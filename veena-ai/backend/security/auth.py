"""Request authentication for the localhost backend.

The Electron main process generates a random token per launch and passes it to
the backend through the environment and to the renderer through the preload
bridge. Every HTTP request and WebSocket must present it, so other local
processes and web pages open in a browser cannot drive the backend.
"""

from __future__ import annotations

import hmac

from fastapi import Request, WebSocket
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

PUBLIC_PATHS = {"/api/health"}


def _token_ok(presented: str | None, expected: str) -> bool:
    return bool(presented) and hmac.compare_digest(presented.encode(), expected.encode())


def _origin_ok(origin: str | None, allowed: tuple[str, ...]) -> bool:
    # Electron loads the renderer from file:// (packaged) or the Vite dev
    # server; both are listed explicitly. "null" is what Chromium sends for
    # file:// pages. Requests without an Origin come from non-browser clients
    # (tests, scripts) and are still gated by the token.
    if origin is None:
        return True
    return origin in allowed or (origin == "null" and "null" in allowed)


class TokenAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str, allowed_origins: tuple[str, ...]):
        super().__init__(app)
        self.token = token
        self.allowed = allowed_origins

    async def dispatch(self, request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)
        if not _origin_ok(request.headers.get("origin"), self.allowed):
            return JSONResponse({"detail": "origin not allowed"}, status_code=403)
        if request.url.path not in PUBLIC_PATHS:
            auth = request.headers.get("authorization", "")
            presented = auth[7:] if auth.lower().startswith("bearer ") else None
            if not _token_ok(presented, self.token):
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)


async def authorize_websocket(ws: WebSocket, token: str, allowed: tuple[str, ...]) -> bool:
    # Browsers cannot set headers on WebSocket upgrades, so the token travels
    # as a subprotocol entry: ["veena", "<token>"].
    if not _origin_ok(ws.headers.get("origin"), allowed):
        await ws.close(code=4403)
        return False
    protos = [p.strip() for p in ws.headers.get("sec-websocket-protocol", "").split(",") if p.strip()]
    presented = protos[1] if len(protos) >= 2 and protos[0] == "veena" else ws.query_params.get("token")
    if not _token_ok(presented, token):
        await ws.close(code=4401)
        return False
    await ws.accept(subprotocol="veena" if protos else None)
    return True
