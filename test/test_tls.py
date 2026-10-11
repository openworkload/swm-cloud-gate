"""mTLS configuration and handshake tests for the cloud gate."""

from __future__ import annotations

import asyncio
import datetime
import ipaddress
import multiprocessing
import os
import socket
import ssl
import tempfile
import time
import unittest
from pathlib import Path

import aiohttp
import uvicorn
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from swmcloudgate.tls import (
    client_cert_allowed,
    cert_sha256_fingerprint_pem,
    uvicorn_ssl_kwargs,
)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _write_cert_key(
    directory: Path,
    common_name: str,
    *,
    issuer_cert: x509.Certificate | None = None,
    issuer_key: rsa.RSAPrivateKey | None = None,
    is_ca: bool = False,
) -> tuple[Path, Path, x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    if issuer_cert is None or issuer_key is None:
        issuer = subject
        signer = key
    else:
        issuer = issuer_cert.subject
        signer = issuer_key
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1))
        .not_valid_after(datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName([x509.IPAddress(ipaddress.IPv4Address("127.0.0.1"))]),
            critical=False,
        )
    )
    if is_ca:
        builder = builder.add_extension(
            x509.BasicConstraints(ca=True, path_length=None),
            critical=True,
        )
    cert = builder.sign(signer, hashes.SHA256())
    cert_path = directory / f"{common_name}-cert.pem"
    key_path = directory / f"{common_name}-key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return cert_path, key_path, cert, key


def _build_spool(root: Path) -> Path:
    """Create a minimal spool/secure tree and return spool/secure path."""
    secure = root / "secure"
    (secure / "cluster").mkdir(parents=True)
    (secure / "node").mkdir(parents=True)
    ca_cert, _ca_key_path, ca_obj, ca_key = _write_cert_key(secure / "cluster", "cluster-ca", is_ca=True)
    # Rename to the paths uvicorn_ssl_kwargs expects.
    cluster_cert = secure / "cluster" / "cert.pem"
    ca_cert.replace(cluster_cert)
    node_cert, node_key, _node_obj, _node_key = _write_cert_key(
        secure / "node",
        "node",
        issuer_cert=ca_obj,
        issuer_key=ca_key,
    )
    (secure / "node" / "cert.pem").write_bytes(node_cert.read_bytes())
    (secure / "node" / "key.pem").write_bytes(node_key.read_bytes())
    node_cert.unlink(missing_ok=True)
    node_key.unlink(missing_ok=True)
    # Keep CA key available for minting a foreign cert in wrong-CA tests.
    (secure / "cluster" / "ca-key.pem").write_bytes(
        ca_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return secure


def _run_uvicorn(host: str, port: int, spool_secure: str) -> None:
    os.environ["SWM_GATE_SPOOL"] = spool_secure
    uvicorn.run(
        "swmcloudgate.main:app",
        host=host,
        port=port,
        log_config=None,
        reload=False,
        timeout_keep_alive=30,
        **uvicorn_ssl_kwargs(spool_secure),
    )


class TestTlsConfig(unittest.TestCase):
    def test_uvicorn_ssl_kwargs_require_client_cert(self) -> None:
        kwargs = uvicorn_ssl_kwargs("/opt/swm/spool/secure")
        self.assertEqual(kwargs["ssl_cert_reqs"], ssl.CERT_REQUIRED)
        self.assertEqual(kwargs["ssl_ca_certs"], "/opt/swm/spool/secure/cluster/cert.pem")
        self.assertEqual(kwargs["ssl_certfile"], "/opt/swm/spool/secure/node/cert.pem")
        self.assertEqual(kwargs["ssl_keyfile"], "/opt/swm/spool/secure/node/key.pem")

    def test_client_cert_allowed_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secure = _build_spool(Path(tmp))
            node = secure / "node" / "cert.pem"
            fp = cert_sha256_fingerprint_pem(str(node))
            der = ssl.PEM_cert_to_DER_cert(node.read_text(encoding="ascii"))
            self.assertTrue(client_cert_allowed(der, str(node)))
            # Foreign cert must not match.
            other_dir = Path(tmp) / "other"
            other_dir.mkdir()
            other_cert, _, _, _ = _write_cert_key(other_dir, "other", is_ca=True)
            other_der = ssl.PEM_cert_to_DER_cert(other_cert.read_text(encoding="ascii"))
            self.assertFalse(client_cert_allowed(other_der, str(node)))
            self.assertNotEqual(fp, cert_sha256_fingerprint_pem(str(other_cert)))


class TestTlsHandshake(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.secure = _build_spool(Path(self.tmp.name))
        self.host = "127.0.0.1"
        self.port = _free_port()
        self.proc = multiprocessing.Process(
            target=_run_uvicorn,
            args=(self.host, self.port, str(self.secure)),
            daemon=True,
        )
        self.proc.start()
        await self._wait_for_port()

    async def asyncTearDown(self) -> None:
        if self.proc.is_alive():
            self.proc.terminate()
        self.proc.join(timeout=5)
        self.tmp.cleanup()

    async def _wait_for_port(self, timeout: float = 15.0) -> None:
        deadline = time.time() + timeout
        last: Exception | None = None
        while time.time() < deadline:
            if not self.proc.is_alive():
                self.fail("uvicorn process died before becoming ready")
            try:
                reader, writer = await asyncio.open_connection(self.host, self.port)
                writer.close()
                await writer.wait_closed()
                return
            except OSError as exc:
                last = exc
                await asyncio.sleep(0.1)
        self.fail(f"server not ready on {self.host}:{self.port}: {last}")

    def _client_ssl(self, *, with_cert: bool = True, wrong_ca: bool = False) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_REQUIRED
        ctx.load_verify_locations(cafile=str(self.secure / "cluster" / "cert.pem"))
        if wrong_ca:
            other = Path(self.tmp.name) / "evil"
            other.mkdir(exist_ok=True)
            evil_ca_cert, _, evil_ca_obj, evil_ca_key = _write_cert_key(other, "evil-ca", is_ca=True)
            evil_cert, evil_key, _, _ = _write_cert_key(
                other, "evil-client", issuer_cert=evil_ca_obj, issuer_key=evil_ca_key
            )
            ctx.load_cert_chain(certfile=str(evil_cert), keyfile=str(evil_key))
            # Still verify server with the real cluster CA (server is honest).
            _ = evil_ca_cert
        elif with_cert:
            ctx.load_cert_chain(
                certfile=str(self.secure / "node" / "cert.pem"),
                keyfile=str(self.secure / "node" / "key.pem"),
            )
        return ctx

    async def test_node_client_cert_allowed(self) -> None:
        url = f"https://{self.host}:{self.port}/"
        connector = aiohttp.TCPConnector(ssl=self._client_ssl(with_cert=True))
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(url) as resp:
                # App has no "/" route; TLS + HTTP stack must succeed.
                self.assertIn(resp.status, (404, 405, 200))

    async def test_missing_client_cert_denied(self) -> None:
        url = f"https://{self.host}:{self.port}/"
        connector = aiohttp.TCPConnector(ssl=self._client_ssl(with_cert=False))
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.get(url) as _resp:
                    self.fail("expected TLS handshake failure without client cert")
            except (
                aiohttp.ClientConnectorError,
                aiohttp.ServerDisconnectedError,
                ssl.SSLError,
                OSError,
            ):
                return

    async def test_wrong_ca_client_cert_denied(self) -> None:
        url = f"https://{self.host}:{self.port}/"
        connector = aiohttp.TCPConnector(ssl=self._client_ssl(wrong_ca=True))
        async with aiohttp.ClientSession(connector=connector) as session:
            try:
                async with session.get(url) as _resp:
                    self.fail("expected TLS handshake failure with wrong client CA")
            except (
                aiohttp.ClientConnectorError,
                aiohttp.ServerDisconnectedError,
                ssl.SSLError,
                OSError,
            ):
                return


if __name__ == "__main__":
    unittest.main()
