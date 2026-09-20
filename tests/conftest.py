"""Shared fixtures.

Tests run against a throw-away SQLite file per test (no Docker needed).
Environment variables must be set BEFORE the app is imported.
"""

import os

os.environ["BCRYPT_ROUNDS"] = "4"  # fast hashing in tests
os.environ["SECRET_KEY"] = "test-secret-key-for-pytest-only-0123456789abcdef"

from dataclasses import dataclass  # noqa: E402
from datetime import datetime, timedelta, timezone  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    async_sessionmaker,
    create_async_engine,
)

from app import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import UserRole  # noqa: E402
from app.services import users  # noqa: E402

PASSWORD = "Password123!"


@dataclass
class Account:
    id: int
    username: str
    password: str
    headers: dict


@pytest_asyncio.fixture
async def session_factory(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as http_client:
        yield http_client
    app.dependency_overrides.clear()


async def login(client: AsyncClient, username: str, password: str = PASSWORD) -> dict:
    response = await client.post(
        "/auth/login", data={"username": username, "password": password}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest_asyncio.fixture
async def make_account(client, session_factory):
    """Factory: creates a user directly in the DB and logs in through the API."""

    async def factory(
        username: str, role: UserRole = UserRole.USER, balance: str = "10000"
    ) -> Account:
        async with session_factory() as session:
            user = await users.create_user(
                session,
                username=username,
                email=f"{username}@example.com",
                password=PASSWORD,
                role=role,
            )
            if Decimal(balance) > 0:
                await users.deposit(session, user.id, Decimal(balance))
            user_id = user.id
        headers = await login(client, username)
        return Account(user_id, username, PASSWORD, headers)

    return factory


@pytest_asyncio.fixture
async def admin(make_account) -> Account:
    return await make_account("admin", UserRole.ADMIN, balance="0")


@pytest_asyncio.fixture
async def alice(make_account) -> Account:
    return await make_account("alice")


@pytest_asyncio.fixture
async def bob(make_account) -> Account:
    return await make_account("bob")


def iso(delta: timedelta) -> str:
    return (datetime.now(timezone.utc) + delta).isoformat()


@pytest_asyncio.fixture
async def create_auction(client, admin):
    """Factory: admin creates an artifact and an auction; returns auction id."""

    async def factory(
        starting_price: str = "100",
        starts_in: timedelta = timedelta(minutes=-5),
        ends_in: timedelta = timedelta(hours=1),
    ) -> int:
        artifact = await client.post(
            "/artifacts", json={"name": "Crystal"}, headers=admin.headers
        )
        assert artifact.status_code == 201, artifact.text
        response = await client.post(
            "/auctions",
            json={
                "artifact_id": artifact.json()["id"],
                "starting_price": starting_price,
                "starts_at": iso(starts_in),
                "ends_at": iso(ends_in),
            },
            headers=admin.headers,
        )
        assert response.status_code == 201, response.text
        return response.json()["id"]

    return factory
