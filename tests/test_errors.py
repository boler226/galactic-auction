from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_500_hides_internals():
    async def boom():
        raise RuntimeError("super-secret-internal")

    app.add_api_route("/__boom", boom)
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get("/__boom")
    finally:
        app.router.routes.pop()

    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error"
    assert "request_id" in response.json()
    assert "super-secret-internal" not in response.text
    assert "Traceback" not in response.text
