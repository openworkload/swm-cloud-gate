"""TLS helpers for the Sky Port cloud gate (mTLS).

The gate HTTPS listener must require a client certificate issued by the
cluster CA. Sky Port presents ``secure/node/{cert,key}.pem`` as the client.
"""

from __future__ import annotations

import hashlib
import logging
import os
import ssl
from typing import Any

LOGGER = logging.getLogger("swm")

DEFAULT_SPOOL_SECURE = "/opt/swm/spool/secure"


def spool_secure_dir() -> str:
    """Return the secure spool directory (override with SWM_SPOOL or SWM_GATE_SPOOL)."""
    override = os.environ.get("SWM_GATE_SPOOL")
    if override:
        return override
    spool = os.environ.get("SWM_SPOOL")
    if spool:
        return os.path.join(spool, "secure")
    return DEFAULT_SPOOL_SECURE


def uvicorn_ssl_kwargs(spool_secure: str | None = None) -> dict[str, Any]:
    """Keyword args for ``uvicorn.run`` enabling server TLS + required client certs."""
    spool = spool_secure or spool_secure_dir()
    ca = os.path.join(spool, "cluster", "cert.pem")
    cert = os.path.join(spool, "node", "cert.pem")
    key = os.path.join(spool, "node", "key.pem")
    return {
        "ssl_version": ssl.PROTOCOL_TLS_SERVER,
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
        "ssl_ca_certs": ca,
        "ssl_certfile": cert,
        "ssl_keyfile": key,
    }


def cert_sha256_fingerprint_pem(pem_path: str) -> bytes:
    """SHA-256 fingerprint of the DER encoding of the first cert in a PEM file."""
    with open(pem_path, "rb") as fh:
        pem = fh.read()
    der = ssl.PEM_cert_to_DER_cert(pem.decode("ascii"))
    return hashlib.sha256(der).digest()


def cert_sha256_fingerprint_der(der: bytes) -> bytes:
    return hashlib.sha256(der).digest()


def client_cert_allowed(peer_der: bytes, allowed_node_cert_path: str) -> bool:
    """True when the peer certificate matches the on-disk Sky Port node cert."""
    try:
        expected = cert_sha256_fingerprint_pem(allowed_node_cert_path)
    except OSError as exc:
        LOGGER.error("Cannot read allowed node cert %s: %s", allowed_node_cert_path, exc)
        return False
    return cert_sha256_fingerprint_der(peer_der) == expected
