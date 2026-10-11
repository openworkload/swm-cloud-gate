"""Client certificate fingerprint pin middleware."""

from __future__ import annotations

import datetime
import os
import ssl
import tempfile
import unittest
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

from swmcloudgate.mtls_middleware import ClientCertPinMiddleware, peer_cert_der_from_scope


def _write_self_signed_pem(path: Path) -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.oid.NameOID.COMMON_NAME, "node")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    pem = cert.public_bytes(serialization.Encoding.PEM)
    path.write_bytes(pem)
    return ssl.PEM_cert_to_DER_cert(pem.decode("ascii"))


def _client_with_peer_der(der: bytes) -> TestClient:
    inner = FastAPI()

    @inner.get("/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "1"}

    pinned = ClientCertPinMiddleware(inner)

    async def asgi(scope, receive, send):
        if scope["type"] == "http":
            scope = dict(scope)
            extensions = dict(scope.get("extensions") or {})
            extensions["tls"] = {"client_cert_chain": [der]}
            scope["extensions"] = extensions
        await pinned(scope, receive, send)

    return TestClient(asgi)


class TestPeerCertFromScope(unittest.TestCase):
    def test_missing_extension(self) -> None:
        self.assertIsNone(peer_cert_der_from_scope({}))

    def test_reads_chain(self) -> None:
        scope = {"extensions": {"tls": {"client_cert_chain": [b"\x30\x82abc"]}}}
        self.assertEqual(peer_cert_der_from_scope(scope), b"\x30\x82abc")


class TestClientCertPinMiddleware(unittest.TestCase):
    def tearDown(self) -> None:
        os.environ.pop("SWM_GATE_ALLOWED_CLIENT_CERT", None)

    def test_allows_when_no_peercert(self) -> None:
        app = FastAPI()
        app.add_middleware(ClientCertPinMiddleware)

        @app.get("/ping")
        async def ping() -> dict[str, str]:
            return {"ok": "1"}

        resp = TestClient(app).get("/ping")
        self.assertEqual(resp.status_code, 200)

    def test_rejects_mismatched_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            allowed = Path(tmp) / "node.pem"
            _write_self_signed_pem(allowed)
            os.environ["SWM_GATE_ALLOWED_CLIENT_CERT"] = str(allowed)
            resp = _client_with_peer_der(b"\x30\x82\x01\x00other-cert-bytes").get("/ping")
            self.assertEqual(resp.status_code, 403)

    def test_allows_matching_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            allowed = Path(tmp) / "node.pem"
            der = _write_self_signed_pem(allowed)
            os.environ["SWM_GATE_ALLOWED_CLIENT_CERT"] = str(allowed)
            resp = _client_with_peer_der(der).get("/ping")
            self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
