"""TLS helpers for the Sky Port cloud gate (mTLS).

The gate HTTPS listener must require a client certificate issued by the
cluster CA. Sky Port presents ``secure/node/{cert,key}.pem`` as the client.
"""

from __future__ import annotations

import hashlib
import logging
import os
import ssl
import tempfile
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


def client_trust_ca_file(spool_secure: str) -> str:
    """CA file used to verify Sky Port client certificates.

    Prefer ``cluster/ca-chain-cert.pem`` (grid + cluster). OpenSSL rejects
    node certs when the trust store is only the intermediate
    ``cluster/cert.pem`` (unable to get issuer certificate). Fall back to
    ``cluster/cert.pem`` for self-signed lab CAs that have no chain file.
    """
    chain = os.path.join(spool_secure, "cluster", "ca-chain-cert.pem")
    if os.path.isfile(chain):
        return chain
    return os.path.join(spool_secure, "cluster", "cert.pem")


def _ssl_certfile_path(cert_path: str) -> str:
    """Return a PEM path safe for ssl.load_cert_chain (strip openssl text prefix)."""
    with open(cert_path, "rb") as fh:
        raw = fh.read()
    text = raw.decode("ascii", errors="strict")
    if text.lstrip().startswith("-----BEGIN CERTIFICATE-----"):
        return cert_path
    clean = _first_cert_pem_block(text)
    fd, tmp = tempfile.mkstemp(prefix="swm-gate-cert-", suffix=".pem")
    try:
        os.write(fd, clean.encode("ascii"))
    finally:
        os.close(fd)
    LOGGER.info("Using cleaned node cert PEM at %s (source had non-PEM prefix)", tmp)
    return tmp


def uvicorn_ssl_kwargs(spool_secure: str | None = None) -> dict[str, Any]:
    """Keyword args for ``uvicorn.run`` enabling server TLS + required client certs."""
    spool = spool_secure or spool_secure_dir()
    ca = client_trust_ca_file(spool)
    cert = _ssl_certfile_path(os.path.join(spool, "node", "cert.pem"))
    key = os.path.join(spool, "node", "key.pem")
    return {
        "ssl_version": ssl.PROTOCOL_TLS_SERVER,
        "ssl_cert_reqs": ssl.CERT_REQUIRED,
        "ssl_ca_certs": ca,
        "ssl_certfile": cert,
        "ssl_keyfile": key,
    }


def _first_cert_pem_block(pem_text: str) -> str:
    """Return the first CERTIFICATE PEM block (stdlib ssl is strict about framing)."""
    begin = "-----BEGIN CERTIFICATE-----"
    end = "-----END CERTIFICATE-----"
    start = pem_text.find(begin)
    stop = pem_text.find(end)
    if start < 0 or stop < 0 or stop < start:
        raise ValueError("No CERTIFICATE PEM block found")
    return pem_text[start : stop + len(end)] + "\n"


def cert_sha256_fingerprint_pem(pem_path: str) -> bytes:
    """SHA-256 fingerprint of the DER encoding of the first cert in a PEM file."""
    with open(pem_path, "rb") as fh:
        pem = fh.read()
    der = ssl.PEM_cert_to_DER_cert(_first_cert_pem_block(pem.decode("ascii", errors="strict")))
    return hashlib.sha256(der).digest()


def cert_sha256_fingerprint_der(der: bytes) -> bytes:
    return hashlib.sha256(der).digest()


def client_cert_allowed(peer_der: bytes, allowed_node_cert_path: str) -> bool:
    """True when the peer certificate matches the on-disk Sky Port node cert."""
    try:
        expected = cert_sha256_fingerprint_pem(allowed_node_cert_path)
    except (OSError, ValueError, UnicodeError) as exc:
        LOGGER.error("Cannot read allowed node cert %s: %s", allowed_node_cert_path, exc)
        return False
    if not peer_der:
        return False
    return cert_sha256_fingerprint_der(peer_der) == expected
