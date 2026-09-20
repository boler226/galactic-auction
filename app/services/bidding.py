"""Bid placement with optimistic locking (race condition protection).

Two users bidding at the same moment both read the auction with version N.
Both try `UPDATE auctions ... WHERE id = :id AND version = N`. The database
lets only one of them succeed; the other gets StaleDataError, re-reads the
fresh price and either bids again (if still valid) or is rejected.
"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.models.auction import Auction, AuctionStatus
from app.models.bid import Bid
from app.models.user import User
from app.services.auctions import MAX_RETRIES, effective_status
from app.services.errors import ConflictError, DomainError, NotFoundError


async def place_bid(
    session: AsyncSession, auction_id: int, user_id: int, amount: Decimal
) -> Bid:
    for _ in range(MAX_RETRIES):
        # populate_existing=True forces a fresh read after a rollback/retry
        auction = await session.get(Auction, auction_id, populate_existing=True)
        if auction is None:
            raise NotFoundError("auction not found")
        user = await session.get(User, user_id, populate_existing=True)
        if user is None or not user.is_active:
            raise DomainError("user is not allowed to bid", 403)

        _validate_bid(auction, user, amount)

        auction.current_price = amount
        auction.highest_bidder_id = user_id
        bid = Bid(auction_id=auction_id, user_id=user_id, amount=amount)
        session.add(bid)
        try:
            await session.commit()
        except StaleDataError:
            # somebody else changed the auction between our read and write
            await session.rollback()
            continue
        await session.refresh(bid)
        return bid

    raise ConflictError("auction is too busy right now, please retry")


def _validate_bid(auction: Auction, user: User, amount: Decimal) -> None:
    if effective_status(auction) != AuctionStatus.ACTIVE:
        raise DomainError("auction is not active")
    if auction.highest_bidder_id == user.id:
        raise DomainError("you are already the highest bidder")
    if auction.highest_bidder_id is None:
        if amount < auction.starting_price:
            raise DomainError("bid is lower than the starting price")
    elif amount <= auction.current_price:
        raise DomainError("bid must be higher than the current price")
    if user.balance < amount:
        raise DomainError("insufficient balance")
