"""Request/response logging middleware.

Logs every incoming request and its corresponding response with
structured fields: method, path, query params, user_id, status_code,
and duration in milliseconds. Generates a ``correlation_id`` that
propagates through the entire request lifecycle.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that logs request/response pairs with timing."""

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        # Generate or reuse correlation ID
        correlation_id = request.headers.get(
            "X-Correlation-ID",
            str(uuid.uuid4()),
        )

        # Attach to request state for downstream use
        request.state.correlation_id = correlation_id

        start_time = time.perf_counter()

        # Extract user_id if already set by AuthMiddleware
        user_id: str | None = getattr(request.state, "user_id", None)

        # Build log context
        log_context = {
            "correlation_id": correlation_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": str(request.query_params) if request.query_params else None,
            "user_id": user_id,
        }

        logger.info("request_started %s %s", request.method, request.url.path, extra=log_context)

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        log_context.update({
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        })

        logger.info(
            "request_finished %s %s -> %s (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            extra=log_context,
        )

        # Propagate correlation ID in response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response
