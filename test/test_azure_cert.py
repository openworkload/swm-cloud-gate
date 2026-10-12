"""Azure certificate is loaded from gate-local files, not HTTP bodies."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from swmcloudgate.azure_cert import AzureCertificateError, load_azure_certificate_data
from swmcloudgate.config import get_settings


class TestAzureCertificateLoad(unittest.TestCase):
    def setUp(self) -> None:
        get_settings.cache_clear()
        os.environ.pop("SWM_GATE_CONFIG", None)
        os.environ.pop("SWM_GATE_SPOOL", None)
        os.environ.pop("SWM_SPOOL", None)

    def tearDown(self) -> None:
        get_settings.cache_clear()
        os.environ.pop("SWM_GATE_CONFIG", None)
        os.environ.pop("SWM_GATE_SPOOL", None)
        os.environ.pop("SWM_SPOOL", None)

    def test_loads_from_spool_node_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secure = Path(tmp) / "secure"
            node = secure / "node"
            node.mkdir(parents=True)
            (node / "key.pem").write_bytes(b"KEY\n")
            (node / "cert.pem").write_bytes(b"CERT\n")
            os.environ["SWM_GATE_SPOOL"] = str(secure)
            # Minimal config without certificate_path
            cfg = Path(tmp) / "cloud-gate.yaml"
            cfg.write_text(
                "version: 1\nbase:\n  cache_dir: ~/.swm/cache\nproviders:\n  azure:\n"
                "    api_credentials:\n      subscription_id: s\n      tenant_id: t\n"
                "      app_id: a\n",
                encoding="utf-8",
            )
            os.environ["SWM_GATE_CONFIG"] = str(cfg)
            get_settings.cache_clear()
            self.assertEqual(load_azure_certificate_data(), b"KEY\nCERT\n")

    def test_certificate_path_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pem = Path(tmp) / "azure.pem"
            pem.write_bytes(b"COMBINED\n")
            cfg = Path(tmp) / "cloud-gate.yaml"
            cfg.write_text(
                "version: 1\nbase:\n  cache_dir: ~/.swm/cache\nproviders:\n  azure:\n"
                "    api_credentials:\n      subscription_id: s\n      tenant_id: t\n"
                f"      app_id: a\n      certificate_path: {pem}\n",
                encoding="utf-8",
            )
            os.environ["SWM_GATE_CONFIG"] = str(cfg)
            get_settings.cache_clear()
            self.assertEqual(load_azure_certificate_data(), b"COMBINED\n")

    def test_missing_spool_files_raise(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            secure = Path(tmp) / "secure"
            secure.mkdir()
            os.environ["SWM_GATE_SPOOL"] = str(secure)
            cfg = Path(tmp) / "cloud-gate.yaml"
            cfg.write_text(
                "version: 1\nbase:\n  cache_dir: ~/.swm/cache\nproviders: {}\n",
                encoding="utf-8",
            )
            os.environ["SWM_GATE_CONFIG"] = str(cfg)
            get_settings.cache_clear()
            with self.assertRaises(AzureCertificateError):
                load_azure_certificate_data()


if __name__ == "__main__":
    unittest.main()
