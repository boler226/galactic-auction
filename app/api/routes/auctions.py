import json

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin, require_user
from app.db.session import get_session
from app.models.auction import Auction
from app.models.bid import Bid
from app.models.user import User
from app.realtime import manager
from app.schemas.auction import AuctionCreate, AuctionOut, BidCreate, BidOut
from app.services import auctions as auction_service
from app.services.bidding import place_bid
from app.services.errors import NotFoundError

router = APIRouter(prefix="/auctions", tags=["auctions"])


async def _get_or_404(session: AsyncSession, auction_id: int) -> Auction:
    auction = await session.get(Auction, auction_id)
    if auction is None:
        raise NotFoundError("auction not found")
    return auction


@router.get("", response_model=list[AuctionOut])
async def list_auctions(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(Auction).order_by(Auction.id.desc()).limit(limit).offset(offset)
    )
    return [auction_service.to_out(a) for a in result.scalars().all()]


@router.get("/{auction_id}", response_model=AuctionOut)
async def get_auction(auction_id: int, session: AsyncSession = Depends(get_session)):
    return auction_service.to_out(await _get_or_404(session, auction_id))


@router.post("", response_model=AuctionOut, status_code=status.HTTP_201_CREATED)
async def create_auction(
    data: AuctionCreate,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    auction = await auction_service.create_auction(session, data)
    return auction_service.to_out(auction)


@router.post("/{auction_id}/close", response_model=AuctionOut)
async def close_auction(
    auction_id: int,
    _: User = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
):
    auction = await auction_service.close_auction(session, auction_id)
    await manager.broadcast(
        auction_id,
        json.dumps(
            {
                "type": "auction_closed",
                "auction_id": auction_id,
                "winner_id": auction.highest_bidder_id,
                "final_price": str(auction.current_price),
            }
        ),
    )
    return auction_service.to_out(auction)


@router.post(
    "/{auction_id}/bids", response_model=BidOut, status_code=status.HTTP_201_CREATED
)
async def create_bid(
    auction_id: int,
    data: BidCreate,
    current_user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Place a bid. Only regular users can bid (admins organise auctions)."""
    user_id = current_user.id  # read before the service may roll back the session
    bid = await place_bid(session, auction_id, user_id, data.amount)
    await manager.broadcast(
        auction_id,
        json.dumps(
            {
                "type": "new_bid",
                "auction_id": auction_id,
                "user_id": bid.user_id,
                "amount": str(bid.amount),
            }
        ),
    )
    return bid


@router.get("/{auction_id}/bids", response_model=list[BidOut])
async def list_bids(
    auction_id: int,
    limit: int = Query(50, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    await _get_or_404(session, auction_id)
    result = await session.execute(
        select(Bid)
        .where(Bid.auction_id == auction_id)
        .order_by(Bid.id.desc())
        .limit(limit)
    )
    return result.scalars().all()
