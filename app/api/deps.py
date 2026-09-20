"""Authentication and authorization dependencies."""

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models.user import User, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session),
) -> User:
    """401 for a missing/invalid/expired token.

    The role is always read from the database, NOT from the token, so a
    forged or outdated `role` claim gives no privileges and a demoted or
    deactivated user loses access immediately."""
    try:
        payload = decode_access_token(token)
        user_id = int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _unauthorized()

    user = await session.get(User, user_id)
    if user is None:
        raise _unauthorized()
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    return user


def require_role(*roles: UserRole):
    """Vertical access control: 403 if the user's role is not allowed."""

    async def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return dependency


require_admin = require_role(UserRole.ADMIN)
require_user = require_role(UserRole.USER)


def ensure_self_or_admin(current_user: User, target_user_id: int) -> None:
    """Horizontal access control (IDOR protection).

    Called BEFORE loading the target object, so a regular user gets 403 both
    for other people's ids and for non-existent ids (no user enumeration)."""
    if current_user.role != UserRole.ADMIN and current_user.id != target_user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access to this resource denied")
