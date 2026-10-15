"""FastAPI debug off and generic error bodies (no stack traces to clients)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from swmcloudgate.config import get_settings


class TestFastapiDebugOff(unittest.TestCase):
    def test_app_debug_is_false(self) -> None:
        from swmcloudgate.main import app

        self.assertFalse(app.debug)


class TestUnhandledExceptionBody(unittest.TestCase):
    def setUp(self) -> None:
        os.environ.setdefault("SWM_GATE_DISABLE_PEER_CERT_PATCH", "1")
        from swmcloudgate.main import app

        self.app = app
        self._path = "/_test_unhandled_error_issue26"

        @app.get(self._path)
        async def _boom() -> dict[str, str]:
            raise RuntimeError("subscription-leak-test-id-should-not-appear")

        self.client = TestClient(app, raise_server_exceptions=False)

    def test_unhandled_exception_returns_generic_500(self) -> None:
        resp = self.client.get(self._path)
        self.assertEqual(resp.status_code, 500)
        body = resp.text
        self.assertNotIn("Traceback", body)
        self.assertNotIn('File "', body)
        self.assertNotIn("subscription-leak-test-id-should-not-appear", body)
        self.assertEqual(resp.json().get("detail"), "Internal server error")


class TestAzurePartitionErrorBodies(unittest.TestCase):
    def setUp(self) -> None:
        self._env = os.environ.copy()
        os.environ["SWM_GATE_DISABLE_PEER_CERT_PATCH"] = "1"
        os.environ["SWM_TEST_CONFIG"] = "test/data/responses.json"
        os.environ["SWM_GATE_CONFIG"] = "test/data/cloud-gate.yaml"
        get_settings.cache_clear()
        from swmcloudgate.main import app
        from swmcloudgate.routers.azure import partitions as azure_partitions

        self.azure_partitions = azure_partitions
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._env)
        get_settings.cache_clear()

    def test_list_partitions_exception_is_generic_500(self) -> None:
        with patch.object(
            self.azure_partitions.CONNECTOR,
            "reinitialize",
            side_effect=RuntimeError("tenant-id-should-not-leak"),
        ):
            resp = self.client.get("/azure/partitions")
        self.assertEqual(resp.status_code, 500)
        body = resp.text
        self.assertNotIn("Traceback", body)
        self.assertNotIn('File "', body)
        self.assertNotIn("tenant-id-should-not-leak", body)
        self.assertEqual(resp.json().get("detail"), "Cannot list partitions")

    def test_value_error_still_returns_400_detail(self) -> None:
        with (
            patch.object(
                self.azure_partitions.CONNECTOR,
                "reinitialize",
                return_value=None,
            ),
            patch.object(
                self.azure_partitions.CONNECTOR,
                "create_deployment",
                side_effect=ValueError("invalid port 99999"),
            ),
        ):
            resp = self.client.post(
                "/azure/partitions",
                headers={
                    "jobid": "40565124-9c03-11ee-8ca4-a3132f7ae2fb",
                    "partname": "part1",
                    "osversion": "ubuntu-hpc/2404",
                    "containerimage": "swmregistry.azurecr.io/img:tag",
                    "flavorname": "Standard_B2s",
                    "username": "azureuser",
                    "count": "1",
                    "runtime": "swm_source=ssh",
                    "location": "eastus2",
                    "ports": "10001",
                },
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("invalid port", resp.json().get("detail", ""))
        self.assertNotIn("Traceback", resp.text)


if __name__ == "__main__":
    unittest.main()
