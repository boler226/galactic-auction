from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ensure_self_or_admin, get_current_user
from app.core.security import hash_password
from app.db.session import get_session
from app.models.bid import Bid
from app.models.user import User
from app.schemas.auction import BidOut
from app.schemas.user import DepositRequest, UserOut, UserUpdate
from app.services import users

router = APIRouter(prefix="/users", tags=["users"])


async def _get_or_404(session: AsyncSession, user_id: int) -> User:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return user


# NOTE: /me must be declared before /{user_id}
@router.get("/me", response_model=UserOut)
async def read_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/{user_id}", response_model=UserOut)
async def read_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ensure_self_or_admin(current_user, user_id)
    return await _get_or_404(session, user_id)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: int,
    data: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Change e-mail / password of a profile (own profile, or any for admin)."""
    ensure_self_or_admin(current_user, user_id)
    user = await _get_or_404(session, user_id)
    if data.email is not None:
        user.email = data.email
    if data.password is not None:
        user.hashed_password = await hash_password(data.password)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "E-mail is already in use")
    await session.refresh(user)
    return user


@router.post("/{user_id}/deposit", response_model=UserOut)
async def deposit(
    user_id: int,
    data: DepositRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Top up the balance (demo payment: no real money involved)."""
    ensure_self_or_admin(current_user, user_id)
    await _get_or_404(session, user_id)
    return await users.deposit(session, user_id, data.amount)


@router.get("/{user_id}/bids", response_model=list[BidOut])
async def user_bids(
    user_id: int,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    ensure_self_or_admin(current_user, user_id)
    await _get_or_404(session, user_id)
    result = await session.execute(
        select(Bid).where(Bid.user_id == user_id).order_by(Bid.id.desc()).limit(100)
    )
    return result.scalars().all()
