"""Authenticated WebSocket channel for real-time auction events.

Connect: ws://host/ws/auctions/{id}?token=<JWT>
The channel is read-only for clients: bids are placed via REST
(POST /auctions/{id}/bids) and the server broadcasts them to the room.
Any client message except "ping" is ignored, so nobody can inject fake prices.

The token is validated statelessly (signature + expiry), without a DB query,
because WebSocket connections are long-lived and numerous.
"""

import jwt
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from app.core.security import decode_access_token
from app.realtime import manager

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/auctions/{auction_id}")
async def auction_room(
    websocket: WebSocket, auction_id: int, token: str | None = Query(default=None)
) -> None:
    try:
        if token is None:
            raise jwt.InvalidTokenError("missing token")
        decode_access_token(token)
    except jwt.PyJWTError:
        # closing before accept() rejects the handshake
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await manager.connect(auction_id, websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(auction_id, websocket)
