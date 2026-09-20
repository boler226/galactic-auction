"""Horizontal access control (IDOR): users must not touch each other's data."""

import pytest


def own_and_foreign(alice, bob):
    return [
        ("GET", f"/users/{bob.id}", None),
        ("PATCH", f"/users/{bob.id}", {"email": "hacked@example.com"}),
        ("POST", f"/users/{bob.id}/deposit", {"amount": "500"}),
        ("GET", f"/users/{bob.id}/bids", None),
    ]


async def test_user_can_not_access_another_users_data(client, alice, bob, admin):
    before = (await client.get(f"/users/{bob.id}", headers=admin.headers)).json()

    for method, path, body in own_and_foreign(alice, bob):
        response = await client.request(method, path, json=body, headers=alice.headers)
        assert response.status_code == 403, (method, path)

    # nothing was changed by the rejected requests
    after = (await client.get(f"/users/{bob.id}", headers=admin.headers)).json()
    assert after == before


async def test_user_can_work_with_own_profile(client, alice):
    own = await client.get(f"/users/{alice.id}", headers=alice.headers)
    assert own.status_code == 200

    patch = await client.patch(
        f"/users/{alice.id}",
        json={"email": "New.Alice@Example.com"},
        headers=alice.headers,
    )
    assert patch.status_code == 200
    assert patch.json()["email"] == "new.alice@example.com"

    bids = await client.get(f"/users/{alice.id}/bids", headers=alice.headers)
    assert bids.status_code == 200
    assert bids.json() == []


async def test_user_can_deposit_only_to_own_balance(client, alice, bob, admin):
    deposit = await client.post(
        f"/users/{alice.id}/deposit", json={"amount": "250.50"}, headers=alice.headers
    )
    assert deposit.status_code == 200
    assert deposit.json()["balance"] in ("10250.50", "10250.5")

    stolen = await client.post(
        f"/users/{bob.id}/deposit", json={"amount": "1"}, headers=alice.headers
    )
    assert stolen.status_code == 403


@pytest.mark.parametrize("amount", ["0", "-5", "abc", "2000000"])
async def test_deposit_rejects_invalid_amount(client, alice, amount):
    response = await client.post(
        f"/users/{alice.id}/deposit", json={"amount": amount}, headers=alice.headers
    )
    assert response.status_code == 422


async def test_foreign_id_gives_403_and_missing_id_does_not_leak_existence(
    client, alice, admin
):
    """A regular user gets 403 for existing AND non-existing ids, so ids can
    not be enumerated. An admin (allowed everywhere) sees the real 404."""
    assert (await client.get("/users/99999", headers=alice.headers)).status_code == 403
    assert (await client.get("/users/99999", headers=admin.headers)).status_code == 404


async def test_admin_can_access_any_profile(client, admin, alice):
    assert (
        await client.get(f"/users/{alice.id}", headers=admin.headers)
    ).status_code == 200
    patch = await client.patch(
        f"/users/{alice.id}",
        json={"email": "by.admin@example.com"},
        headers=admin.headers,
    )
    assert patch.status_code == 200
    bids = await client.get(f"/users/{alice.id}/bids", headers=admin.headers)
    assert bids.status_code == 200


@pytest.mark.parametrize(
    "payload",
    [{"role": "admin"}, {"is_active": False}, {"balance": "999999"}, {"id": 1}],
)
async def test_profile_update_rejects_privileged_fields(client, alice, payload):
    """Mass assignment: privileged fields are rejected, not silently applied."""
    response = await client.patch(
        f"/users/{alice.id}", json=payload, headers=alice.headers
    )
    assert response.status_code == 422
    me = (await client.get("/users/me", headers=alice.headers)).json()
    assert me["role"] == "user" and me["is_active"] is True


async def test_email_of_another_user_can_not_be_taken(client, alice, bob):
    response = await client.patch(
        f"/users/{alice.id}", json={"email": "bob@example.com"}, headers=alice.headers
    )
    assert response.status_code == 409


async def test_users_only_see_their_own_bids(client, alice, bob, create_auction):
    auction_id = await create_auction()
    placed = await client.post(
        f"/auctions/{auction_id}/bids", json={"amount": "150"}, headers=alice.headers
    )
    assert placed.status_code == 201

    mine = await client.get(f"/users/{alice.id}/bids", headers=alice.headers)
    assert [b["amount"] for b in mine.json()] in (["150.00"], ["150"], ["150.0"])
    stolen = await client.get(f"/users/{alice.id}/bids", headers=bob.headers)
    assert stolen.status_code == 403
