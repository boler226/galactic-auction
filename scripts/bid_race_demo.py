"""Demonstration of race-condition protection.

Creates an auction, registers N users and makes all of them bid AT THE SAME
MOMENT (different amounts). Then checks the invariants:
  * the highest attempted bid is never lost;
  * accepted bids form a strictly rising sequence.

Run the server first, then:
    python scripts/bid_race_demo.py --admin-password "Admin12345!"
"""

import argparse
import asyncio
import secrets
from collections import Counter
from datetime import datetime, timedelta, timezone

import httpx


async def login(client: httpx.AsyncClient, username: str, password: str) -> dict:
    response = await client.post(
        "/auth/login", data={"username": username, "password": password}
    )
    response.raise_for_status()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def make_bidder(client: httpx.AsyncClient, tag: str, index: int) -> dict:
    username, password = f"race_{tag}_{index}", "Password123!"
    response = await client.post(
        "/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        },
    )
    response.raise_for_status()
    user_id = response.json()["id"]
    headers = await login(client, username, password)
    await client.post(
        f"/users/{user_id}/deposit", json={"amount": "100000"}, headers=headers
    )
    return {"id": user_id, "headers": headers}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--admin-user", default="admin")
    parser.add_argument("--admin-password", required=True)
    parser.add_argument("--bidders", type=int, default=20)
    args = parser.parse_args()

    async with httpx.AsyncClient(base_url=args.base_url, timeout=60) as client:
        admin = await login(client, args.admin_user, args.admin_password)
        artifact = await client.post(
            "/artifacts", json={"name": "Race Demo Relic"}, headers=admin
        )
        now = datetime.now(timezone.utc)
        auction = await client.post(
            "/auctions",
            json={
                "artifact_id": artifact.json()["id"],
                "starting_price": "10",
                "starts_at": (now - timedelta(minutes=1)).isoformat(),
                "ends_at": (now + timedelta(hours=1)).isoformat(),
            },
            headers=admin,
        )
        auction_id = auction.json()["id"]

        tag = secrets.token_hex(3)
        print(f"Preparing {args.bidders} bidders ...")
        bidders = await asyncio.gather(
            *(make_bidder(client, tag, i) for i in range(args.bidders))
        )
        amounts = [100 + 10 * i for i in range(args.bidders)]

        print(f"Auction #{auction_id}: {args.bidders} simultaneous bids ...")
        responses = await asyncio.gather(
            *(
                client.post(
                    f"/auctions/{auction_id}/bids",
                    json={"amount": str(amount)},
                    headers=bidder["headers"],
                )
                for bidder, amount in zip(bidders, amounts)
            )
        )
        print("HTTP results:", dict(Counter(r.status_code for r in responses)))

        final = (await client.get(f"/auctions/{auction_id}")).json()
        history = (await client.get(f"/auctions/{auction_id}/bids?limit=100")).json()
        accepted = [float(b["amount"]) for b in reversed(history)]

    print("Accepted bids in order:", accepted)
    print(
        "Final price:", final["current_price"], "| leader:", final["highest_bidder_id"]
    )

    ok_top = float(final["current_price"]) == max(amounts)
    ok_order = accepted == sorted(set(accepted))
    print("Highest bid preserved :", "OK" if ok_top else "FAIL")
    print("Strictly rising order :", "OK" if ok_order else "FAIL")
    return 0 if ok_top and ok_order else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
