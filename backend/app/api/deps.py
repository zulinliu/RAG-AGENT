"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.config import get_settings
from app.database import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_redis(request: Request):
    """Return the Redis connection pool stored on app.state."""
    redis_client = getattr(request.app.state, "redis", None)
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis connection not available")
    return redis_client


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict[str, Any]:
    """Decode the JWT token and return the user payload.

    Returns a dict with keys: user_id, username, role, project_ids.
    """
    settings = get_settings()
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(
            token,
            settings.auth.secret_key,
            algorithms=[settings.auth.algorithm],
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except jwt.InvalidTokenError as exc:
        raise credentials_exception from exc

    user_id: str | None = payload.get("user_id")
    if user_id is None:
        raise credentials_exception

    return payload


# Re-export get_db so that route modules can import from a single location.
__all__ = ["get_db", "get_current_user", "get_redis"]
