"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from app.database import get_db
from app.utils.auth import get_current_user, verify_token


async def get_redis(request: Request):
    """Return the Redis connection pool stored on app.state."""
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis connection not available")
    return redis_client


# Re-export get_db so that route modules can import from a single location.
__all__ = ["get_db", "get_current_user", "get_redis", "verify_token"]
