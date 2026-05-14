"""Health-check route — verifies connectivity to every backing service."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", summary="Service health check")
async def health_check(request: Request) -> JSONResponse:
    """Return the connection status of PostgreSQL, Redis, Milvus and Elasticsearch."""
    checks: dict[str, str] = {}

    # --- PostgreSQL ---
    try:
        from sqlalchemy import text

        from app.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgresql"] = "ok"
    except Exception:
        logger.exception("postgresql health check failed")
        checks["postgresql"] = "error"

    # --- Redis ---
    try:
        redis_client = request.app.state.redis
        if redis_client is None:
            checks["redis"] = "error"
        else:
            await redis_client.ping()
            checks["redis"] = "ok"
    except Exception:
        logger.exception("redis health check failed")
        checks["redis"] = "error"

    # --- Milvus (use shared client from app.state) ---
    try:
        milvus_client = request.app.state.milvus_client
        if milvus_client is None:
            checks["milvus"] = "error"
        else:
            # MilvusClient.list_collections() is a lightweight liveness probe
            milvus_client.list_collections()
            checks["milvus"] = "ok"
    except Exception:
        logger.exception("milvus health check failed")
        checks["milvus"] = "error"

    # --- Elasticsearch (use shared client from app.state) ---
    try:
        es_client = request.app.state.es_client
        if es_client is None:
            checks["elasticsearch"] = "error"
        else:
            await es_client.ping()
            checks["elasticsearch"] = "ok"
    except Exception:
        logger.exception("elasticsearch health check failed")
        checks["elasticsearch"] = "error"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if overall == "ok" else 503

    return JSONResponse(
        content={"status": overall, "services": checks},
        status_code=status_code,
    )
