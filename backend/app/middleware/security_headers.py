"""Security headers middleware (pure ASGI).

Adds standard security response headers to every HTTP response:
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - Referrer-Policy: strict-origin-when-cross-origin
  - Permissions-Policy: camera=(), microphone=(), geolocation=()

Uses a pure ASGI implementation so that streaming responses (SSE)
are not buffered or broken.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Message, Receive, Scope, Send

SECURITY_HEADERS: dict[bytes, bytes] = {
    b"x-content-type-options": b"nosniff",
    b"x-frame-options": b"DENY",
    b"referrer-policy": b"strict-origin-when-cross-origin",
    b"permissions-policy": b"camera=(), microphone=(), geolocation=()",
}


class SecurityHeadersMiddleware:
    """Pure ASGI middleware that injects security headers into every response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_security_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {name.lower() for name, _ in headers}
                for name, value in SECURITY_HEADERS.items():
                    if name not in existing:
                        headers.append((name, value))
                message = {
                    "type": message["type"],
                    "status": message.get("status", 200),
                    "headers": headers,
                }
            await send(message)

        await self.app(scope, receive, send_with_security_headers)
