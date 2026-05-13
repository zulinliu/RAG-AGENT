"""Health-check route — verifies connectivity to every backing service."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

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
    except Exception as exc:
        checks["postgresql"] = f"error: {exc}"

    # --- Redis ---
    try:
        redis_client = request.app.state.redis
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:
        checks["redis"] = f"error: {exc}"

    # --- Milvus ---
    try:
        from pymilvus import connections

        from app.config import get_settings

        settings = get_settings()
        connections.connect(
            alias="health",
            host=settings.milvus.host,
            port=settings.milvus.port,
            user=settings.milvus.user or "",
            password=settings.milvus.password or "",
        )
        connections.disconnect("health")
        checks["milvus"] = "ok"
    except Exception as exc:
        checks["milvus"] = f"error: {exc}"

    # --- Elasticsearch ---
    try:
        from elasticsearch import AsyncElasticsearch

        from app.config import get_settings

        settings = get_settings()
        es = AsyncElasticsearch(
            hosts=[settings.es.hosts],
            basic_auth=(settings.es.user, settings.es.password),
        )
        await es.ping()
        await es.close()
        checks["elasticsearch"] = "ok"
    except Exception as exc:
        checks["elasticsearch"] = f"error: {exc}"

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    status_code = 200 if overall == "ok" else 503

    return JSONResponse(
        content={"status": overall, "services": checks},
        status_code=status_code,
    )
