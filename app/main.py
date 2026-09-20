from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import health, ws
from app.core.config import settings
from app.db.session import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="High-load galactic artifact auction (Lab 1 skeleton).",
        lifespan=lifespan,
    )
    application.include_router(health.router)
    application.include_router(ws.router)
    return application


app = create_app()
