from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_liveness() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_websocket_broadcast() -> None:
    with client.websocket_connect("/ws/auctions/1") as first:
        with client.websocket_connect("/ws/auctions/1") as second:
            first.send_text("bid:100")
            assert first.receive_text() == "bid:100"
            assert second.receive_text() == "bid:100"
