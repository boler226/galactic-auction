"""Home page stubs for every user type."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user, require_admin, require_user
from app.models.user import User, UserRole

router = APIRouter(prefix="/home", tags=["home"])


@router.get("")
async def home_redirect(current_user: User = Depends(get_current_user)):
    """Tells the client which home page belongs to the current role."""
    target = "/home/admin" if current_user.role == UserRole.ADMIN else "/home/user"
    return {"role": current_user.role, "home": target}


@router.get("/user")
async def user_home(current_user: User = Depends(require_user)):
    return {
        "page": "user_home",
        "message": f"Welcome, {current_user.username}! Here will be your auctions.",
        "balance": current_user.balance,
    }


@router.get("/admin")
async def admin_home(current_user: User = Depends(require_admin)):
    return {
        "page": "admin_home",
        "message": f"Welcome, administrator {current_user.username}!",
    }
