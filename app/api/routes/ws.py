"""WebSocket skeleton for real-time bidding.

NOTE: this is an in-memory placeholder. In later labs the connection
manager will be backed by Redis Pub/Sub so that several application
instances behind a load balancer can share auction rooms, and bid
processing will be moved to a race-condition-safe service.
"""

from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, auction_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._rooms[auction_id].add(websocket)

    def disconnect(self, auction_id: int, websocket: WebSocket) -> None:
        self._rooms[auction_id].discard(websocket)
        if not self._rooms[auction_id]:
            del self._rooms[auction_id]

    async def broadcast(self, auction_id: int, message: str) -> None:
        for connection in list(self._rooms.get(auction_id, ())):
            await connection.send_text(message)


manager = ConnectionManager()


@router.websocket("/ws/auctions/{auction_id}")
async def auction_room(websocket: WebSocket, auction_id: int) -> None:
    await manager.connect(auction_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(auction_id, data)
    except WebSocketDisconnect:
        manager.disconnect(auction_id, websocket)
