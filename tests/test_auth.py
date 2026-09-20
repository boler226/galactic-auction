"""Anonymous access, registration, login and token handling."""

from datetime import datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy import select

from app.core.config import settings
from app.core.security import create_access_token
from app.models.user import User, UserRole
from tests.conftest import PASSWORD

# (method, path) of every protected endpoint
PROTECTED = [
    ("GET", "/users/me"),
    ("GET", "/users/1"),
    ("PATCH", "/users/1"),
    ("POST", "/users/1/deposit"),
    ("GET", "/users/1/bids"),
    ("GET", "/home"),
    ("GET", "/home/user"),
    ("GET", "/home/admin"),
    ("GET", "/admin/users"),
    ("GET", "/admin/stats"),
    ("PATCH", "/admin/users/1"),
    ("POST", "/artifacts"),
    ("POST", "/auctions"),
    ("POST", "/auctions/1/close"),
    ("POST", "/auctions/1/bids"),
]


# ---------- anonymous access ----------
@pytest.mark.parametrize("method,path", PROTECTED)
async def test_anonymous_gets_401(client, method, path):
    response = await client.request(method, path, json={})
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_public_endpoints_do_not_need_login(client):
    for path in ("/health", "/artifacts", "/auctions"):
        assert (await client.get(path)).status_code == 200


async def test_garbage_token_gets_401(client):
    response = await client.get("/users/me", headers={"Authorization": "Bearer abc"})
    assert response.status_code == 401


async def test_expired_token_gets_401(client, alice):
    expired = jwt.encode(
        {
            "sub": str(alice.id),
            "role": "user",
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        settings.secret_key,
        algorithm=settings.jwt_algorithm,
    )
    response = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {expired}"}
    )
    assert response.status_code == 401


async def test_token_signed_with_wrong_key_gets_401(client, alice):
    forged = jwt.encode(
        {
            "sub": str(alice.id),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "attacker-key-attacker-key-attacker-key-0000",
        algorithm="HS256",
    )
    response = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {forged}"}
    )
    assert response.status_code == 401


async def test_unsigned_token_alg_none_gets_401(client, alice):
    unsigned = jwt.encode({"sub": str(alice.id)}, key=None, algorithm="none")
    response = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {unsigned}"}
    )
    assert response.status_code == 401


async def test_token_of_deleted_user_gets_401(client):
    token = create_access_token(user_id=9999, role="user")
    response = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 401


# ---------- registration ----------
async def register(client, **overrides):
    payload = {
        "username": "newbie",
        "email": "newbie@example.com",
        "password": PASSWORD,
    }
    payload.update(overrides)
    return await client.post("/auth/register", json=payload)


async def test_register_creates_regular_user(client, session_factory):
    response = await register(client)
    assert response.status_code == 201
    body = response.json()
    assert body["role"] == "user"
    assert body["is_active"] is True
    assert "password" not in body and "hashed_password" not in body

    async with session_factory() as session:
        user = (await session.execute(select(User))).scalar_one()
    assert user.hashed_password != PASSWORD  # never stored in plain text
    assert user.hashed_password.startswith("$2b$")


async def test_register_normalises_username_and_email(client):
    response = await register(client, username="NewBie", email="NewBie@Example.COM")
    assert response.status_code == 201
    assert response.json()["username"] == "newbie"
    assert response.json()["email"] == "newbie@example.com"


async def test_register_duplicate_username_or_email_gets_409(client):
    assert (await register(client)).status_code == 201
    same_username = await register(client, email="other@example.com")
    same_email = await register(client, username="other")
    assert same_username.status_code == 409
    assert same_email.status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "short"},
        {"password": "x" * 73},
        {"username": "ab"},
        {"username": "bad name!"},
        {"email": "not-an-email"},
    ],
)
async def test_register_rejects_invalid_data(client, overrides):
    assert (await register(client, **overrides)).status_code == 422


async def test_cannot_register_as_admin(client, session_factory):
    """Privilege escalation via mass assignment must not work."""
    response = await register(client, role="admin")
    assert response.status_code == 422
    async with session_factory() as session:
        admins = await session.execute(select(User).where(User.role == UserRole.ADMIN))
        assert admins.first() is None


# ---------- login ----------
async def test_login_success_returns_working_token(client, alice):
    response = await client.post(
        "/auth/login", data={"username": "alice", "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"

    me = await client.get(
        "/users/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


async def test_login_is_case_insensitive_for_username(client, alice):
    response = await client.post(
        "/auth/login", data={"username": "ALICE", "password": PASSWORD}
    )
    assert response.status_code == 200


async def test_login_wrong_password_gets_401(client, alice):
    response = await client.post(
        "/auth/login", data={"username": "alice", "password": "WrongPassword1"}
    )
    assert response.status_code == 401


async def test_login_unknown_user_gets_401(client):
    response = await client.post(
        "/auth/login", data={"username": "ghost", "password": PASSWORD}
    )
    assert response.status_code == 401


async def test_login_errors_do_not_reveal_which_part_is_wrong(client, alice):
    wrong_password = await client.post(
        "/auth/login", data={"username": "alice", "password": "WrongPassword1"}
    )
    unknown_user = await client.post(
        "/auth/login", data={"username": "ghost", "password": "WrongPassword1"}
    )
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


async def test_login_after_register_full_flow(client):
    assert (await register(client)).status_code == 201
    login_response = await client.post(
        "/auth/login", data={"username": "newbie", "password": PASSWORD}
    )
    assert login_response.status_code == 200


async def test_login_of_password_less_legacy_account_fails(client, session_factory):
    """Rows created before the auth migration have an empty hash."""
    async with session_factory() as session:
        session.add(
            User(username="legacy", email="legacy@example.com", hashed_password="")
        )
        await session.commit()
    response = await client.post(
        "/auth/login", data={"username": "legacy", "password": PASSWORD}
    )
    assert response.status_code == 401
