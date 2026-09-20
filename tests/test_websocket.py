"""WebSocket authentication and the connection manager."""

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token
from app.main import app
from app.realtime import ConnectionManager

ws_client = TestClient(app)


def test_ws_rejects_connection_without_token():
    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_client.websocket_connect("/ws/auctions/1"):
            pass
    assert exc.value.code == 1008


def test_ws_rejects_invalid_token():
    with pytest.raises(WebSocketDisconnect) as exc:
        with ws_client.websocket_connect("/ws/auctions/1?token=garbage"):
            pass
    assert exc.value.code == 1008


def test_ws_accepts_valid_token_and_answers_ping():
    token = create_access_token(user_id=1, role="user")
    with ws_client.websocket_connect(f"/ws/auctions/1?token={token}") as ws:
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


class FakeSocket:
    def __init__(self, fail=False):
        self.fail = fail
        self.messages = []

    async def accept(self):
        pass

    async def send_text(self, text):
        if self.fail:
            raise RuntimeError("connection lost")
        self.messages.append(text)


async def test_manager_broadcasts_only_to_its_room_and_drops_dead_sockets():
    manager = ConnectionManager()
    alive, dead, other = FakeSocket(), FakeSocket(fail=True), FakeSocket()
    await manager.connect(1, alive)
    await manager.connect(1, dead)
    await manager.connect(2, other)

    await manager.broadcast(1, "hello")

    assert alive.messages == ["hello"]
    assert other.messages == []
    await manager.broadcast(1, "again")  # dead socket was removed, no crash
    assert alive.messages == ["hello", "again"]
