"""MVP business logic: artifacts, auctions, bids, closing."""

import asyncio
import json
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm.exc import StaleDataError

from app.models.auction import Auction
from app.models.bid import Bid
from app.realtime import manager
from app.services.bidding import place_bid
from app.services.errors import DomainError
from tests.conftest import iso


async def bid(client, account, auction_id, amount):
    return await client.post(
        f"/auctions/{auction_id}/bids",
        json={"amount": str(amount)},
        headers=account.headers,
    )


# ---------- artifacts & auctions ----------
async def test_artifacts_are_public_to_read(client, admin):
    created = await client.post(
        "/artifacts",
        json={"name": "Orion Sphere", "rarity": "epic"},
        headers=admin.headers,
    )
    assert created.status_code == 201
    assert (await client.get("/artifacts")).json()[0]["name"] == "Orion Sphere"
    assert (await client.get(f"/artifacts/{created.json()['id']}")).status_code == 200
    assert (await client.get("/artifacts/999")).status_code == 404


async def test_create_auction_validation(client, admin, create_auction):
    await create_auction()  # makes artifact 1

    def body(**overrides):
        payload = {
            "artifact_id": 1,
            "starting_price": "100",
            "starts_at": iso(timedelta(minutes=-1)),
            "ends_at": iso(timedelta(hours=1)),
        }
        payload.update(overrides)
        return payload

    post = lambda payload: client.post(  # noqa: E731
        "/auctions", json=payload, headers=admin.headers
    )
    assert (await post(body(artifact_id=999))).status_code == 404
    assert (await post(body(ends_at=iso(timedelta(hours=-2))))).status_code == 422
    assert (await post(body(starting_price="-1"))).status_code == 422
    # naive datetime (no timezone) is refused
    assert (await post(body(ends_at="2030-01-01T10:00:00"))).status_code == 422


async def test_auction_status_is_derived_from_time(client, create_auction):
    active = await create_auction()
    scheduled = await create_auction(
        starts_in=timedelta(hours=1), ends_in=timedelta(hours=2)
    )
    finished = await create_auction(
        starts_in=timedelta(hours=-2), ends_in=timedelta(hours=-1)
    )
    status = {
        name: (await client.get(f"/auctions/{aid}")).json()["status"]
        for name, aid in [("a", active), ("s", scheduled), ("f", finished)]
    }
    assert status == {"a": "active", "s": "scheduled", "f": "finished"}


# ---------- bidding ----------
async def test_bidding_flow(client, alice, bob, create_auction):
    auction_id = await create_auction(starting_price="100")

    first = await bid(client, alice, auction_id, 150)
    assert first.status_code == 201
    assert first.json()["user_id"] == alice.id

    auction = (await client.get(f"/auctions/{auction_id}")).json()
    assert Decimal(auction["current_price"]) == 150
    assert auction["highest_bidder_id"] == alice.id

    assert (await bid(client, bob, auction_id, 150)).status_code == 400  # equal
    assert (await bid(client, bob, auction_id, 120)).status_code == 400  # lower
    assert (await bid(client, bob, auction_id, 200)).status_code == 201
    assert (await bid(client, bob, auction_id, 300)).status_code == 400  # own lead
    assert (await bid(client, alice, auction_id, 250)).status_code == 201

    history = (await client.get(f"/auctions/{auction_id}/bids")).json()
    assert [Decimal(b["amount"]) for b in history] == [250, 200, 150]


async def test_first_bid_must_reach_starting_price(client, alice, create_auction):
    auction_id = await create_auction(starting_price="100")
    assert (await bid(client, alice, auction_id, 99)).status_code == 400
    assert (await bid(client, alice, auction_id, 100)).status_code == 201


async def test_bid_needs_enough_balance(client, make_account, create_auction):
    poor = await make_account("poor", balance="50")
    auction_id = await create_auction(starting_price="10")
    assert (await bid(client, poor, auction_id, 51)).status_code == 400
    assert (await bid(client, poor, auction_id, 50)).status_code == 201


async def test_bid_on_inactive_auction_is_rejected(client, alice, create_auction):
    scheduled = await create_auction(
        starts_in=timedelta(hours=1), ends_in=timedelta(hours=2)
    )
    finished = await create_auction(
        starts_in=timedelta(hours=-2), ends_in=timedelta(hours=-1)
    )
    assert (await bid(client, alice, scheduled, 150)).status_code == 400
    assert (await bid(client, alice, finished, 150)).status_code == 400
    assert (await bid(client, alice, 9999, 150)).status_code == 404


@pytest.mark.parametrize("amount", ["0", "-10", "abc", "10.999"])
async def test_bid_rejects_invalid_amount(client, alice, create_auction, amount):
    auction_id = await create_auction()
    assert (await bid(client, alice, auction_id, amount)).status_code == 422


async def test_admin_closes_auction_and_winner_is_fixed(
    client, admin, alice, bob, create_auction
):
    auction_id = await create_auction()
    await bid(client, alice, auction_id, 150)
    await bid(client, bob, auction_id, 200)

    assert (
        await client.post(f"/auctions/{auction_id}/close", headers=alice.headers)
    ).status_code == 403
    closed = await client.post(f"/auctions/{auction_id}/close", headers=admin.headers)
    assert closed.status_code == 200
    assert closed.json()["status"] == "finished"
    assert closed.json()["highest_bidder_id"] == bob.id

    assert (await bid(client, alice, auction_id, 500)).status_code == 400
    again = await client.post(f"/auctions/{auction_id}/close", headers=admin.headers)
    assert again.status_code == 409


# ---------- race condition protection ----------
async def test_optimistic_lock_rejects_stale_write(session_factory, create_auction):
    """Two transactions read the same auction version; only one may win."""
    auction_id = await create_auction()
    async with session_factory() as first, session_factory() as second:
        a1 = await first.get(Auction, auction_id)
        a2 = await second.get(Auction, auction_id)

        a1.current_price = Decimal("150")
        await first.commit()

        a2.current_price = Decimal("120")  # based on stale data
        with pytest.raises(StaleDataError):
            await second.commit()


async def test_concurrent_bids_never_lose_the_highest_bid(
    session_factory, make_account, create_auction
):
    """10 users bid at the same moment with different amounts."""
    auction_id = await create_auction(starting_price="10")
    bidders = [await make_account(f"user{i}") for i in range(10)]
    amounts = {b.id: Decimal(100 + 10 * i) for i, b in enumerate(bidders)}

    async def attempt(user_id: int):
        async with session_factory() as session:
            return await place_bid(session, auction_id, user_id, amounts[user_id])

    results = await asyncio.gather(
        *(attempt(b.id) for b in bidders), return_exceptions=True
    )
    # the only acceptable failures are business rejections, never crashes
    assert all(r is None or isinstance(r, (Bid, DomainError)) for r in results)

    async with session_factory() as session:
        auction = await session.get(Auction, auction_id)
        bids = (await session.execute(select(Bid).order_by(Bid.id))).scalars().all()

    accepted = [b.amount for b in bids]
    assert accepted, "at least one bid must be accepted"
    assert accepted == sorted(accepted), "accepted bids must be strictly rising"
    assert len(set(accepted)) == len(accepted)
    # the highest of all attempted bids can never be lost
    assert auction.current_price == max(amounts.values())
    assert auction.current_price == accepted[-1]


# ---------- real-time notification ----------
class FakeWebSocket:
    def __init__(self):
        self.messages = []

    async def accept(self):
        pass

    async def send_text(self, text):
        self.messages.append(text)


async def test_accepted_bid_is_broadcast_to_room(client, alice, create_auction):
    auction_id = await create_auction()
    listener, other_room = FakeWebSocket(), FakeWebSocket()
    await manager.connect(auction_id, listener)
    await manager.connect(auction_id + 1000, other_room)
    try:
        await bid(client, alice, auction_id, 150)
        await bid(client, alice, auction_id, 120)  # rejected: nothing broadcast
    finally:
        manager.disconnect(auction_id, listener)
        manager.disconnect(auction_id + 1000, other_room)

    assert len(listener.messages) == 1
    event = json.loads(listener.messages[0])
    assert event == {
        "type": "new_bid",
        "auction_id": auction_id,
        "user_id": alice.id,
        "amount": event["amount"],
    }
    assert Decimal(event["amount"]) == 150
    assert other_room.messages == []
