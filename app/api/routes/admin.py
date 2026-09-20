"""Admin panel. Every endpoint requires the `admin` role."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_session
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.user import User, UserRole
from app.schemas.user import AdminUserUpdate, UserOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=list[UserOut])
async def list_users(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(User).order_by(User.id).limit(limit).offset(offset)
    )
    return result.scalars().all()


@router.patch("/users/{user_id}", response_model=UserOut)
async def update_user_by_admin(
    user_id: int,
    data: AdminUserUpdate,
    admin: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    """Change role or block/unblock a user."""
    if user_id == admin.id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Admins can not change their own role/status"
        )
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    if data.role is not None:
        user.role = data.role
    if data.is_active is not None:
        user.is_active = data.is_active
    await session.commit()
    await session.refresh(user)
    return user


@router.get("/stats")
async def stats(
    _: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
):
    users_count = await session.scalar(select(func.count(User.id)))
    admins_count = await session.scalar(
        select(func.count(User.id)).where(User.role == UserRole.ADMIN)
    )
    auctions_count = await session.scalar(select(func.count(Auction.id)))
    bids_count = await session.scalar(select(func.count(Bid.id)))
    return {
        "users": users_count,
        "admins": admins_count,
        "auctions": auctions_count,
        "bids": bids_count,
    }
