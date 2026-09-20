from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import admin, artifacts, auctions, auth, health, home, users, ws
from app.core.config import settings
from app.db.session import engine
from app.services.errors import DomainError


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
    return application


app = create_app()
