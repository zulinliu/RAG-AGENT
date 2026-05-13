"""FastAPI application entry point."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.health import router as health_router
from app.api.router import api_router
from app.config import get_settings
from app.database import engine
from app.middleware.auth import AuthMiddleware
from app.middleware.logging import LoggingMiddleware
from app.utils.logging import configure_logging


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Manage startup and shutdown lifecycle events."""
    settings = get_settings()

    # ---- startup ----
    configure_logging(environment=settings.environment)

    # Redis connection pool
    application.state.redis = aioredis.from_url(
        settings.redis.url,
        decode_responses=True,
        max_connections=20,
    )

    yield

    # ---- shutdown ----
    if application.state.redis is not None:
        await application.state.redis.aclose()

    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.is_development else [],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware (added in reverse order: last added = first executed)
    application.add_middleware(AuthMiddleware)
    application.add_middleware(LoggingMiddleware)

    # ---- routes ----
    application.include_router(health_router)
    application.include_router(api_router)

    return application


app = create_app()
