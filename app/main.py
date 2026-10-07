from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import admin, artifacts, auctions, auth, health, home, users, ws
from app.core.config import settings
from app.db.session import engine
from app.services.errors import DomainError

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.2.0",
        description="High-load galactic artifact auction. Lab 2: users and roles.",
        lifespan=lifespan,
    )

    @application.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    for router in (
        health.router,
        auth.router,
        users.router,
        home.router,
        admin.router,
        artifacts.router,
        auctions.router,
        ws.router,
    ):
        application.include_router(router)

    # Frontend: single-page UI served by the same process (no CORS needed).
    application.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @application.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return application


app = create_app()
