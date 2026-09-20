from datetime import datetime
from decimal import Decimal

from pydantic import AwareDatetime, BaseModel, ConfigDict, model_validator

from app.models.auction import AuctionStatus
from app.schemas.common import Money


class AuctionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: int
    starting_price: Money
    starts_at: AwareDatetime
    ends_at: AwareDatetime

    @model_validator(mode="after")
    def check_dates(self) -> "AuctionCreate":
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class AuctionOut(BaseModel):
    id: int
    artifact_id: int
    starting_price: Decimal
    current_price: Decimal
    highest_bidder_id: int | None
    status: AuctionStatus
    starts_at: datetime
    ends_at: datetime


class BidCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Money


class BidOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    auction_id: int
    user_id: int
    amount: Decimal
    created_at: datetime
