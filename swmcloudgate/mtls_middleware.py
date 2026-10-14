"""Application-level client certificate fingerprint pin (when peercert is visible)."""

from __future__ import annotations

import os
import logging
from typing import Any, Callable, Awaitable

from starlette.responses import JSONResponse

from .tls import spool_secure_dir, client_cert_allowed

LOGGER = logging.getLogger("swm")

Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


def peer_cert_der_from_scope(scope: dict[str, Any]) -> bytes | None:
    """Return the first peer cert DER from ASGI TLS extension, if present."""
    extensions = scope.get("extensions") or {}
    tls = extensions.get("tls") or {}
    chain = tls.get("client_cert_chain") or []
    if not chain:
        return None
    der = chain[0]
    if isinstance(der, (bytes, bytearray)) and der:
        return bytes(der)
    return None


def allowed_client_cert_path() -> str:
    override = os.environ.get("SWM_GATE_ALLOWED_CLIENT_CERT", "").strip()
    if override:
        return override
    return os.path.join(spool_secure_dir(), "node", "cert.pem")


class ClientCertPinMiddleware:
    """Pure ASGI middleware: pin peer cert fingerprint to the node cert when visible.

    Uses a plain ASGI wrapper (not Starlette BaseHTTPMiddleware) to avoid
    known request-hang issues with uvicorn workers under mTLS.

    If peercert is absent (TestClient, or uvicorn without the peercert patch),
    the request proceeds. Handshake ``CERT_REQUIRED`` still applies for HTTPS.
    """

    def __init__(self, app: Callable) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        der = peer_cert_der_from_scope(scope)
        if der is None:
            await self.app(scope, receive, send)
            return
        path = allowed_client_cert_path()
        if not client_cert_allowed(der, path):
            LOGGER.warning("Rejected client certificate (fingerprint mismatch)")
            response = JSONResponse({"detail": "client certificate not allowed"}, status_code=403)
            await response(scope, receive, send)
            return
        await self.app(scope, receive, send)
