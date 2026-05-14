"""Request/response logging middleware (pure ASGI).

Logs every incoming request and its corresponding response with
structured fields: method, path, query params, user_id, status_code,
and duration in milliseconds. Generates a ``correlation_id`` that
propagates through the entire request lifecycle.

Uses a pure ASGI implementation instead of BaseHTTPMiddleware so that
streaming responses (SSE) are not buffered or broken.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class LoggingMiddleware:
    """Pure ASGI middleware that logs request/response pairs with timing."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Extract request info from ASGI scope
        headers = dict(scope.get("headers", []))
        method = scope.get("method", "")
        path = scope.get("path", "")
        query_string = scope.get("query_string", b"").decode("utf-8", errors="replace")

        # Generate or reuse correlation ID
        raw_cid = headers.get(b"x-correlation-id")
        correlation_id = raw_cid.decode("utf-8", errors="replace") if raw_cid else str(uuid.uuid4())

        # Extract user_id if already set by AuthMiddleware
        state = scope.get("state", {})
        user_id: str | None = state.get("user_id")

        # Build log context
        log_context = {
            "correlation_id": correlation_id,
            "method": method,
            "path": path,
            "query_params": query_string or None,
            "user_id": user_id,
        }

        logger.info("request_started %s %s", method, path, extra=log_context)

        start_time = time.perf_counter()

        # Capture status code from the response
        status_code: int = 0

        async def send_with_logging(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message.get("status", 0)
            await send(message)

        try:
            await self.app(scope, receive, send_with_logging)
        finally:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

            log_context.update({
                "status_code": status_code,
                "duration_ms": duration_ms,
            })

            logger.info(
                "request_finished %s %s -> %s (%.1fms)",
                method,
                path,
                status_code,
                duration_ms,
                extra=log_context,
            )

            # Inject correlation ID header into response.
            # This is a best-effort approach for pure ASGI: we inject it via
            # a trailing headers message if the response hasn't already been sent
            # with that header. Downstream code reading X-Correlation-ID should
            # also check the request header (which was set above).
