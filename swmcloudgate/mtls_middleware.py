"""Application-level client certificate fingerprint pin (when peercert is visible)."""

from __future__ import annotations

import logging
import os
from typing import Any, Callable, Awaitable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .tls import client_cert_allowed, spool_secure_dir

LOGGER = logging.getLogger("swm")


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


class ClientCertPinMiddleware(BaseHTTPMiddleware):
    """When the ASGI scope exposes a peer cert, require it match the node cert.

    If peercert is absent (TestClient, or uvicorn without the peercert patch),
    the request proceeds. Handshake ``CERT_REQUIRED`` still applies for HTTPS.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        der = peer_cert_der_from_scope(request.scope)
        if der is None:
            return await call_next(request)
        path = allowed_client_cert_path()
        if not client_cert_allowed(der, path):
            LOGGER.warning("Rejected client certificate (fingerprint mismatch)")
            return JSONResponse({"detail": "client certificate not allowed"}, status_code=403)
        return await call_next(request)
