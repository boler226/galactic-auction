"""Management commands.

    python -m app.cli create-admin --username admin --email admin@example.com
    python -m app.cli seed-demo

Admins can not register through the public API (by design): they are created
here, by someone with access to the server.
"""

import argparse
import asyncio
import getpass
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import func, select

from app.db.session import SessionLocal, engine
from app.models.artifact import Artifact
from app.models.auction import Auction
from app.models.user import UserRole
from app.schemas.auction import AuctionCreate
from app.schemas.user import UserRegister
from app.services import auctions as auction_service
from app.services import users
from app.services.errors import ConflictError

DEMO_ADMIN = ("admin", "admin@example.com", "Admin12345!")
DEMO_USERS = [
    ("alice", "alice@example.com", "Password123!", Decimal("5000")),
    ("bob", "bob@example.com", "Password123!", Decimal("3000")),
]
DEMO_ARTIFACTS = [
    ("Crystal of Andromeda", "Glows in the presence of dark matter", "legendary"),
    ("Orion Navigation Sphere", "Ancient star map, still works", "epic"),
    ("Nebula Shard", "Fragment of a collapsed nebula", "rare"),
]


async def _create(username: str, email: str, password: str, role: UserRole) -> bool:
    try:
        data = UserRegister(username=username, email=email, password=password)
    except ValidationError as exc:
        print(f"Invalid data:\n{exc}")
        return False
    async with SessionLocal() as session:
        try:
            await users.create_user(
                session,
                username=data.username,
                email=data.email,
                password=data.password,
                role=role,
            )
        except ConflictError:
            print(f"User '{data.username}' (or e-mail) already exists, skipped")
            return False
    print(f"Created {role.value}: {data.username}")
    return True


async def create_admin(username: str, email: str, password: str | None) -> int:
    if password is None:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match")
            return 1
    return 0 if await _create(username, email, password, UserRole.ADMIN) else 1


async def seed_demo() -> int:
    await _create(*DEMO_ADMIN, UserRole.ADMIN)
    for username, email, password, balance in DEMO_USERS:
        if await _create(username, email, password, UserRole.USER):
            async with SessionLocal() as session:
                user = await users.get_by_username(session, username)
                await users.deposit(session, user.id, balance)

    async with SessionLocal() as session:
        if not await session.scalar(select(func.count(Artifact.id))):
            session.add_all(
                Artifact(name=n, description=d, rarity=r, origin_galaxy="Andromeda")
                for n, d, r in DEMO_ARTIFACTS
            )
            await session.commit()
            print(f"Created {len(DEMO_ARTIFACTS)} artifacts")

        if not await session.scalar(select(func.count(Auction.id))):
            artifact = (await session.execute(select(Artifact).limit(1))).scalar_one()
            now = datetime.now(timezone.utc)
            await auction_service.create_auction(
                session,
                AuctionCreate(
                    artifact_id=artifact.id,
                    starting_price=Decimal("100"),
                    starts_at=now - timedelta(minutes=1),
                    ends_at=now + timedelta(hours=2),
                ),
            )
            print("Created 1 active auction (2 hours)")

    print("\nDemo accounts:")
    print(f"  admin: {DEMO_ADMIN[0]} / {DEMO_ADMIN[2]}")
    for username, _, password, _ in DEMO_USERS:
        print(f"  user:  {username} / {password}")
    return 0


async def _run(args: argparse.Namespace) -> int:
    try:
        if args.command == "create-admin":
            return await create_admin(args.username, args.email, args.password)
        return await seed_demo()
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    admin = sub.add_parser("create-admin", help="create an administrator")
    admin.add_argument("--username", required=True)
    admin.add_argument("--email", required=True)
    admin.add_argument("--password", help="omit to be prompted securely")
    sub.add_parser("seed-demo", help="create demo users, artifacts and an auction")

    sys.exit(asyncio.run(_run(parser.parse_args())))


if __name__ == "__main__":
    main()
