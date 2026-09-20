"""In-memory WebSocket rooms (one room per auction).

NOTE: state lives inside one process. With several backend instances behind
a load balancer this will be replaced by Redis Pub/Sub (next labs).
"""

import asyncio
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[int, set[WebSocket]] = defaultdict(set)

    async def connect(self, auction_id: int, websocket: WebSocket) -> None:
        await websocket.accept()
        self._rooms[auction_id].add(websocket)

    def disconnect(self, auction_id: int, websocket: WebSocket) -> None:
        room = self._rooms.get(auction_id)
        if room is None:
            return
        room.discard(websocket)
        if not room:
            del self._rooms[auction_id]

    async def broadcast(self, auction_id: int, message: str) -> None:
        connections = list(self._rooms.get(auction_id, ()))
        results = await asyncio.gather(
            *(conn.send_text(message) for conn in connections),
            return_exceptions=True,
        )
        for conn, result in zip(connections, results):
            if isinstance(result, Exception):  # dead connection
                self.disconnect(auction_id, conn)


manager = ConnectionManager()
