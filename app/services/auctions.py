from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.models.artifact import Artifact
from app.models.auction import Auction, AuctionStatus
from app.schemas.auction import AuctionCreate, AuctionOut
from app.services.errors import ConflictError, NotFoundError

MAX_RETRIES = 3


def as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; PostgreSQL returns aware ones."""
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def effective_status(auction: Auction, now: datetime | None = None) -> AuctionStatus:
    """Status is derived from time, except for an explicit close by an admin."""
    now = now or datetime.now(timezone.utc)
    if auction.status == AuctionStatus.FINISHED:
        return AuctionStatus.FINISHED
    if now < as_utc(auction.starts_at):
        return AuctionStatus.SCHEDULED
    if now >= as_utc(auction.ends_at):
        return AuctionStatus.FINISHED
    return AuctionStatus.ACTIVE


def to_out(auction: Auction) -> AuctionOut:
    return AuctionOut(
        id=auction.id,
        artifact_id=auction.artifact_id,
        starting_price=auction.starting_price,
        current_price=auction.current_price,
        highest_bidder_id=auction.highest_bidder_id,
        status=effective_status(auction),
        starts_at=auction.starts_at,
        ends_at=auction.ends_at,
    )


async def create_auction(session: AsyncSession, data: AuctionCreate) -> Auction:
    if await session.get(Artifact, data.artifact_id) is None:
        raise NotFoundError("artifact not found")
    now = datetime.now(timezone.utc)
    auction = Auction(
        artifact_id=data.artifact_id,
        starting_price=data.starting_price,
        current_price=data.starting_price,
        status=(
            AuctionStatus.ACTIVE if data.starts_at <= now else AuctionStatus.SCHEDULED
        ),
        starts_at=data.starts_at,
        ends_at=data.ends_at,
    )
    session.add(auction)
    await session.commit()
    await session.refresh(auction)
    return auction


async def close_auction(session: AsyncSession, auction_id: int) -> Auction:
    """Finish an auction. Uses the same optimistic locking as bidding, so a bid
    that arrives at the same moment can not be silently lost."""
    for _ in range(MAX_RETRIES):
        auction = await session.get(Auction, auction_id, populate_existing=True)
        if auction is None:
            raise NotFoundError("auction not found")
        if auction.status == AuctionStatus.FINISHED:
            raise ConflictError("auction is already closed")
        auction.status = AuctionStatus.FINISHED
        try:
            await session.commit()
        except StaleDataError:
            await session.rollback()
            continue
        return auction
    raise ConflictError("auction is busy, retry the request")
