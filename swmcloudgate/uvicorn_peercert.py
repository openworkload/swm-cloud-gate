"""Inject TLS peer cert DER into the ASGI scope for uvicorn.

Stock uvicorn HTTP protocols do not populate ``scope["extensions"]["tls"]``.
This patch reads ``ssl_object.getpeercert(binary_form=True)`` from the
transport and stores it as ``client_cert_chain`` (ASGI TLS extension shape)
so middleware can pin the client certificate fingerprint.
"""

from __future__ import annotations

import logging
from typing import Any

LOGGER = logging.getLogger("swm")

_INSTALLED = False


def _peer_der_from_transport(transport: Any) -> bytes | None:
    if transport is None:
        return None
    try:
        ssl_object = transport.get_extra_info("ssl_object")
    except Exception:
        return None
    if ssl_object is None:
        return None
    try:
        der = ssl_object.getpeercert(binary_form=True)
    except Exception:
        return None
    if not der:
        return None
    return der


def _wrap_cycle_init(cycle_cls: type) -> None:
    if getattr(cycle_cls, "_swm_peercert_wrapped", False):
        return
    original_init = cycle_cls.__init__

    def wrapped_init(self, scope, *args, **kwargs):  # type: ignore[no-untyped-def]
        original_init(self, scope, *args, **kwargs)
        der = _peer_der_from_transport(getattr(self, "transport", None))
        if der is None:
            return
        extensions = scope.setdefault("extensions", {})
        tls = extensions.setdefault("tls", {})
        tls.setdefault("client_cert_chain", [der])

    cycle_cls.__init__ = wrapped_init  # type: ignore[method-assign]
    cycle_cls._swm_peercert_wrapped = True


def install() -> None:
    """Patch uvicorn HTTP RequestResponseCycle classes (idempotent)."""
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        from uvicorn.protocols.http import h11_impl

        _wrap_cycle_init(h11_impl.RequestResponseCycle)
    except Exception as exc:
        LOGGER.debug("uvicorn h11 peercert patch skipped: %s", exc)
    try:
        from uvicorn.protocols.http import httptools_impl

        _wrap_cycle_init(httptools_impl.RequestResponseCycle)
    except Exception as exc:
        LOGGER.debug("uvicorn httptools peercert patch skipped: %s", exc)
    _INSTALLED = True
