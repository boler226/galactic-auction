import re
from datetime import datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
)

from app.models.user import UserRole
from app.schemas.common import Money

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,32}$")


def _validate_password(value: str) -> str:
    # bcrypt only uses the first 72 bytes, so we reject longer passwords.
    if len(value.encode("utf-8")) > 72:
        raise ValueError("password must be at most 72 bytes long")
    return value


class UserRegister(BaseModel):
    """Public registration. Role is NOT accepted: extra fields are rejected,
    so nobody can register themselves as an admin (mass assignment)."""

    model_config = ConfigDict(extra="forbid")

    username: str
    email: EmailStr
    password: str = Field(min_length=8)

    @field_validator("username")
    @classmethod
    def check_username(cls, value: str) -> str:
        if not USERNAME_RE.match(value):
            raise ValueError("username: 3-32 chars, letters, digits and underscore")
        return value.lower()

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str) -> str:
        return _validate_password(value)


class UserUpdate(BaseModel):
    """Profile update. Role / balance / is_active can NOT be changed here."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)

    @field_validator("email")
    @classmethod
    def lower_email(cls, value: str | None) -> str | None:
        return value.lower() if value else value

    @field_validator("password")
    @classmethod
    def check_password(cls, value: str | None) -> str | None:
        return _validate_password(value) if value is not None else value


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: UserRole | None = None
    is_active: bool | None = None


class DepositRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Money = Field(le=Decimal("1000000"))


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    role: UserRole
    is_active: bool
    balance: Decimal
    created_at: datetime
