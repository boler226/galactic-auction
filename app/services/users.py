from decimal import Decimal

from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, verify_password
from app.models.user import User, UserRole
from app.services.errors import ConflictError


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    result = await session.execute(select(User).where(User.username == username))
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    password: str,
    role: UserRole = UserRole.USER,
) -> User:
    exists = await session.execute(
        select(User.id).where(or_(User.username == username, User.email == email))
    )
    if exists.first() is not None:
        raise ConflictError("username or email already registered")

    user = User(
        username=username,
        email=email,
        hashed_password=await hash_password(password),
        role=role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:  # concurrent registration with the same data
        await session.rollback()
        raise ConflictError("username or email already registered") from exc
    await session.refresh(user)
    return user


async def authenticate(
    session: AsyncSession, username: str, password: str
) -> User | None:
    """Return the user if credentials are valid, otherwise None.
    Same code path (and similar timing) for unknown user and wrong password."""
    user = await get_by_username(session, username.lower())
    hashed = user.hashed_password if user else None
    if not await verify_password(password, hashed):
        return None
    return user


async def deposit(session: AsyncSession, user_id: int, amount: Decimal) -> User:
    """Atomic balance increase: done in SQL, so concurrent deposits
    can never overwrite each other (no lost update)."""
    await session.execute(
        update(User).where(User.id == user_id).values(balance=User.balance + amount)
    )
    await session.commit()
    user = await session.get(User, user_id, populate_existing=True)
    assert user is not None
    return user
