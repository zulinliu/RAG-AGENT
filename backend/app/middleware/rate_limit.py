"""Redis-based rate limiting middleware (pure ASGI).

Uses a sliding-window counter in Redis to enforce per-IP and per-user
rate limits on configured path prefixes.

Limit strategy:
  - /api/v1/auth/login : 10 requests/minute per IP
  - /api/v1/qa/*       : 20 requests/minute per user
  - /api/v1/* (default): 60 requests/minute per IP
"""

from __future__ import annotations

import logging
import time
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

# Path-specific limits: (prefix, limit, window_seconds)
_PATH_LIMITS: list[tuple[str, int, int]] = [
    ("/api/v1/auth/login", 10, 60),
    ("/api/v1/qa/", 20, 60),
]

# Default limit for any unmatched /api/v1/ path
_DEFAULT_LIMIT = 60
_DEFAULT_WINDOW = 60


class RateLimitMiddleware:
    """Pure ASGI middleware that enforces rate limits via Redis."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http",):
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive, send)
        path = request.url.path

        # Only rate-limit API paths
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # Determine applicable limit
        limit, window = _DEFAULT_LIMIT, _DEFAULT_WINDOW
        for prefix, lim, win in _PATH_LIMITS:
            if path.startswith(prefix):
                limit, window = lim, win
                break

        # Identify the client: per-user if authenticated, otherwise per-IP
        user_id: str | None = None
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                from app.utils.auth import verify_token

                payload = verify_token(auth_header[7:])
                user_id = payload.get("user_id")
            except Exception:
                pass  # unauthenticated — fall back to IP

        client_key = f"user:{user_id}" if user_id else f"ip:{_client_ip(request)}"
        redis_key = f"ratelimit:{client_key}:{path}"

        # Access Redis from app.state
        redis: Any = getattr(request.app.state, "redis", None)
        if redis is None:
            # Redis unavailable — allow request through
            await self.app(scope, receive, send)
            return

        # Sliding window counter
        now = time.time()
        window_start = now - window
        pipe = redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zadd(redis_key, {str(now): now})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, window + 1)
        results = await pipe.execute()
        count = results[2]

        if count > limit:
            response: Response = JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please try again later."},
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


def _client_ip(request: Request) -> str:
    """Extract client IP, respecting reverse-proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
