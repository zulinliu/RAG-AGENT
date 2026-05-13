"""JWT authentication middleware.

Automatically extracts the Bearer token from the Authorization header,
verifies it, and injects ``user_id`` and ``project_permissions`` into the
request state. Paths that do not require authentication are excluded.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.utils.auth import verify_token

logger = logging.getLogger(__name__)

# Paths that bypass authentication entirely
PUBLIC_PATHS: frozenset[str] = frozenset({
    "/health",
    "/",
    "/docs",
    "/redoc",
    "/openapi.json",
})

# Path prefixes that bypass authentication
PUBLIC_PREFIXES: tuple[str, ...] = (
    "/api/v1/auth/login",
    "/api/v1/auth/register",
)


class AuthMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that authenticates requests via JWT.

    On every request:
    1. Check if the path is public -- if so, skip auth.
    2. Extract the ``Authorization: Bearer <token>`` header.
    3. Decode and validate the JWT.
    4. Store ``request.state.user_id``, ``request.state.user_role``,
       and ``request.state.project_ids`` for downstream access.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            return await call_next(request)

        # Skip for non-API paths (static files, etc.)
        if not path.startswith("/api/"):
            return await call_next(request)

        # Extract token
        auth_header: str | None = request.headers.get("Authorization")
        if auth_header is None or not auth_header.startswith("Bearer "):
            # Let the route handler enforce auth -- some endpoints
            # may optionally accept unauthenticated requests.
            request.state.user_id = None
            request.state.user_role = None
            request.state.project_ids = []
            return await call_next(request)

        token = auth_header[len("Bearer "):]
        try:
            payload: dict[str, Any] = verify_token(token)
        except Exception:
            # Token invalid or expired -- the downstream dependency
            # (get_current_user) will raise 401 with details.
            request.state.user_id = None
            request.state.user_role = None
            request.state.project_ids = []
            return await call_next(request)

        # Inject into request state
        request.state.user_id = payload.get("user_id")
        request.state.user_role = payload.get("role")
        request.state.project_ids = payload.get("project_ids", [])

        return await call_next(request)
