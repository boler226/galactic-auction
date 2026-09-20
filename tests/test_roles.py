"""Vertical access control: what each ROLE may do."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import settings
from tests.conftest import iso

AUCTION_BODY = {
    "artifact_id": 1,
    "starting_price": "100",
    "starts_at": iso(timedelta(minutes=-1)),
    "ends_at": iso(timedelta(hours=1)),
}

# Endpoints reserved for administrators: (method, path, json body)
ADMIN_ONLY = [
    ("GET", "/home/admin", None),
    ("GET", "/admin/users", None),
    ("GET", "/admin/stats", None),
    ("PATCH", "/admin/users/1", {"is_active": False}),
    ("POST", "/artifacts", {"name": "Crystal"}),
    ("POST", "/auctions", AUCTION_BODY),
    ("POST", "/auctions/1/close", None),
]


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY)
async def test_regular_user_gets_403_on_admin_endpoints(
    client, alice, method, path, body
):
    response = await client.request(method, path, json=body, headers=alice.headers)
    assert response.status_code == 403


async def test_role_is_checked_before_body_validation(client, alice):
    """A regular user must get 403, not 422 that would leak the schema."""
    response = await client.post("/auctions", json={}, headers=alice.headers)
    assert response.status_code == 403


@pytest.mark.parametrize("method,path,body", ADMIN_ONLY[:3])
async def test_admin_can_use_admin_endpoints(client, admin, method, path, body):
    response = await client.request(method, path, json=body, headers=admin.headers)
    assert response.status_code == 200


async def test_admin_can_create_artifact_and_auction(client, admin, create_auction):
    auction_id = await create_auction()
    response = await client.get(f"/auctions/{auction_id}")
    assert response.status_code == 200
    assert response.json()["status"] == "active"


async def test_each_role_has_its_own_home_page(client, admin, alice):
    user_home = await client.get("/home/user", headers=alice.headers)
    admin_home = await client.get("/home/admin", headers=admin.headers)
    assert user_home.status_code == 200
    assert user_home.json()["page"] == "user_home"
    assert admin_home.status_code == 200
    assert admin_home.json()["page"] == "admin_home"

    assert (await client.get("/home", headers=alice.headers)).json()["home"] == (
        "/home/user"
    )
    assert (await client.get("/home", headers=admin.headers)).json()["home"] == (
        "/home/admin"
    )


async def test_admin_does_not_get_the_user_home_page(client, admin):
    assert (await client.get("/home/user", headers=admin.headers)).status_code == 403


async def test_admin_can_not_bid(client, admin, create_auction):
    auction_id = await create_auction()
    response = await client.post(
        f"/auctions/{auction_id}/bids", json={"amount": "150"}, headers=admin.headers
    )
    assert response.status_code == 403


async def test_forged_role_claim_in_token_gives_no_privileges(client, alice):
    """The role is taken from the DB, so a self-made 'admin' claim is useless
    even if the token is correctly signed."""
    forged = jwt.encode(
        {
            "sub": str(alice.id),
            "role": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {forged}"}
    )
    assert response.status_code == 403


async def test_role_change_takes_effect_immediately(client, admin, alice):
    path = "/admin/users"
    assert (await client.get(path, headers=alice.headers)).status_code == 403

    promote = await client.patch(
        f"/admin/users/{alice.id}", json={"role": "admin"}, headers=admin.headers
    )
    assert promote.status_code == 200
    assert (await client.get(path, headers=alice.headers)).status_code == 200

    demote = await client.patch(
        f"/admin/users/{alice.id}", json={"role": "user"}, headers=admin.headers
    )
    assert demote.status_code == 200
    assert (await client.get(path, headers=alice.headers)).status_code == 403


async def test_blocked_user_loses_access_and_can_not_login(client, admin, alice):
    block = await client.patch(
        f"/admin/users/{alice.id}", json={"is_active": False}, headers=admin.headers
    )
    assert block.status_code == 200

    # the old token stops working ...
    assert (await client.get("/users/me", headers=alice.headers)).status_code == 403
    # ... and a new login is refused
    login = await client.post(
        "/auth/login", data={"username": "alice", "password": alice.password}
    )
    assert login.status_code == 403


async def test_admin_can_not_change_own_role(client, admin):
    response = await client.patch(
        f"/admin/users/{admin.id}", json={"role": "user"}, headers=admin.headers
    )
    assert response.status_code == 400


async def test_admin_user_list_never_exposes_password_hashes(client, admin, alice):
    response = await client.get("/admin/users", headers=admin.headers)
    assert response.status_code == 200
    assert len(response.json()) == 2
    for item in response.json():
        assert "hashed_password" not in item and "password" not in item
