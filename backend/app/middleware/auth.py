"""JWT authentication middleware (pure ASGI).

Automatically extracts the Bearer token from the Authorization header,
verifies it, and injects ``user_id`` and ``project_permissions`` into the
request state. Paths that do not require authentication are excluded.

Uses a pure ASGI implementation instead of BaseHTTPMiddleware so that
streaming responses (SSE) are not buffered or broken.
"""

from __future__ import annotations

import logging
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


class AuthMiddleware:
    """Pure ASGI middleware that authenticates requests via JWT.

    On every request:
    1. Check if the path is public -- if so, skip auth.
    2. Extract the ``Authorization: Bearer <token>`` header.
    3. Decode and validate the JWT.
    4. Store ``request.state.user_id``, ``request.state.user_role``,
       and ``request.state.project_ids`` for downstream access.

    If a non-public path carries an Authorization header with an invalid
    or expired token, the middleware immediately returns 401 instead of
    silently swallowing the error.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        # Build a Request to read headers / path
        request = Request(scope, receive, send)

        path = request.url.path

        # Skip auth for public paths
        if path in PUBLIC_PATHS or any(path.startswith(p) for p in PUBLIC_PREFIXES):
            await self.app(scope, receive, send)
            return

        # Skip for non-API paths (static files, etc.)
        if not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        # Extract token
        auth_header: str | None = request.headers.get("Authorization")
        if auth_header is None or not auth_header.startswith("Bearer "):
            # No token provided on an API path -- set anonymous state and
            # let downstream dependencies (e.g. get_current_user) enforce
            # authentication where required.
            scope.setdefault("state", {})
            scope["state"]["user_id"] = None
            scope["state"]["user_role"] = None
            scope["state"]["project_ids"] = []
            await self.app(scope, receive, send)
            return

        token = auth_header[len("Bearer "):]
        try:
            payload: dict[str, Any] = verify_token(token)
        except Exception:
            # Token is present but invalid/expired -- immediately reject.
            # Avoid silently setting user_id=None which hides auth failures.
            response: Response = JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )
            await response(scope, receive, send)
            return

        # Inject into scope state
        scope.setdefault("state", {})
        scope["state"]["user_id"] = payload.get("user_id")
        scope["state"]["user_role"] = payload.get("role")
        scope["state"]["project_ids"] = payload.get("project_ids", [])

        await self.app(scope, receive, send)
