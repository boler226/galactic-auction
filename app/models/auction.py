import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuctionStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    FINISHED = "finished"


class Auction(Base):
    __tablename__ = "auctions"

    id: Mapped[int] = mapped_column(primary_key=True)
    artifact_id: Mapped[int] = mapped_column(ForeignKey("artifacts.id"), index=True)
    starting_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    current_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    highest_bidder_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    status: Mapped[AuctionStatus] = mapped_column(
        Enum(AuctionStatus, name="auction_status"),
        default=AuctionStatus.SCHEDULED,
        index=True,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Optimistic locking: SQLAlchemy will raise StaleDataError if two
    # concurrent transactions try to update the same auction version.
    # This is the foundation for handling the race condition on bids.
    version: Mapped[int] = mapped_column(default=1)

    __mapper_args__ = {"version_id_col": version}
