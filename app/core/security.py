"""Password hashing and JWT helpers.

Hashing and verification with bcrypt are CPU-bound (~100 ms). They are run
in a worker thread so they never block the asyncio event loop, which matters
for a high-load service.
"""

import asyncio
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

# Pre-computed hash used to keep login timing similar for unknown usernames.
_DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt(rounds=4)).decode()


def _hash_sync(password: str) -> str:
    salt = bcrypt.gensalt(rounds=settings.bcrypt_rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _verify_sync(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hash_sync, password)


async def verify_password(password: str, hashed: str | None) -> bool:
    """Verify a password. `hashed=None` means the user does not exist:
    a dummy check is done so response time does not reveal valid usernames."""
    if hashed is None:
        await asyncio.to_thread(_verify_sync, password, _DUMMY_HASH)
        return False
    return await asyncio.to_thread(_verify_sync, password, hashed)


def create_access_token(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Return the token payload or raise jwt.PyJWTError."""
    return jwt.decode(
        token,
        settings.secret_key,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp"]},
    )
