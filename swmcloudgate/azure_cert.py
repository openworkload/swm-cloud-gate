"""Load Azure AD certificate material from gate-local files (never from HTTP)."""

from __future__ import annotations

import os
from pathlib import Path

from . import config
from .tls import spool_secure_dir


class AzureCertificateError(Exception):
    """Azure SP certificate file missing or empty."""


def load_azure_certificate_data() -> bytes:
    """Return PEM bytes (private key + cert) for CertificateCredential.

    Prefer ``providers.azure.api_credentials.certificate_path`` when set.
    Otherwise use ``$SPOOL/node/key.pem`` + ``cert.pem`` (same node identity
    the gate already uses for TLS).
    """
    try:
        settings = config.get_settings()
        path = (settings.providers.azure.api_credentials.certificate_path or "").strip()
    except FileNotFoundError:
        path = ""

    if path:
        cert_path = Path(path).expanduser()
        try:
            data = cert_path.read_bytes()
        except OSError as exc:
            raise AzureCertificateError(f"Cannot read Azure certificate_path {cert_path}: {exc}") from exc
        if not data:
            raise AzureCertificateError(f"Azure certificate_path is empty: {cert_path}")
        return data

    spool = spool_secure_dir()
    key_path = os.path.join(spool, "node", "key.pem")
    cert_path = os.path.join(spool, "node", "cert.pem")
    try:
        with open(key_path, "rb") as key_fh, open(cert_path, "rb") as cert_fh:
            data = key_fh.read() + cert_fh.read()
    except OSError as exc:
        raise AzureCertificateError(f"Cannot read Azure cert from spool ({key_path}, {cert_path}): {exc}") from exc
    if not data:
        raise AzureCertificateError("Azure spool node key/cert are empty")
    return data
