import os
import unittest
from unittest.mock import MagicMock, patch

import libcloud.security
from fastapi.testclient import TestClient

from swmcloudgate.config import OpenStackProvider, get_settings
from swmcloudgate.routers.openstack.auth import (
    OpenStackAuthError,
    resolve_openstack_credentials,
)
from swmcloudgate.routers.openstack.connector import OpenStackConnector


class TestResolveCredentials(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()
        self._env = os.environ.copy()
        os.environ["SWM_GATE_CONFIG"] = "test/data/cloud-gate.yaml"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        get_settings.cache_clear()

    def test_header_pair_wins(self):
        user, password = resolve_openstack_credentials("hdr-user", "hdr-pass")
        self.assertEqual(user, "hdr-user")
        self.assertEqual(password, "hdr-pass")

    def test_config_fallback_when_headers_empty(self):
        user, password = resolve_openstack_credentials(None, None)
        self.assertEqual(user, "cfg-user")
        self.assertEqual(password, "cfg-password")

    def test_username_only_falls_back_to_config(self):
        # Sky Port sends username without password; use gate config pair.
        user, password = resolve_openstack_credentials("skyport-user", None)
        self.assertEqual(user, "cfg-user")
        self.assertEqual(password, "cfg-password")

    def test_password_only_rejected(self):
        with self.assertRaises(OpenStackAuthError):
            resolve_openstack_credentials(None, "only-pass")

    def test_missing_headers_and_empty_config_rejected(self):
        with patch(
            "swmcloudgate.routers.openstack.auth.load_openstack_provider",
            return_value=OpenStackProvider(),
        ):
            with self.assertRaises(OpenStackAuthError):
                resolve_openstack_credentials(None, None)


class TestOpenStackConnectorAuth(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()
        self._env = os.environ.copy()
        os.environ.pop("SWM_TEST_CONFIG", None)
        os.environ["SWM_GATE_CONFIG"] = "test/data/cloud-gate.yaml"
        self._verify_ssl = libcloud.security.VERIFY_SSL_CERT

    def tearDown(self):
        libcloud.security.VERIFY_SSL_CERT = self._verify_ssl
        os.environ.clear()
        os.environ.update(self._env)
        get_settings.cache_clear()

    def _provider(self, **overrides) -> OpenStackProvider:
        base = dict(
            auth_url="https://keystone.test:5000",
            username="cfg-user",
            password="cfg-password",
            project_name="demo",
            domain_name="Default",
            verify_ssl=True,
            ca_cert="",
            allow_insecure_http=False,
        )
        base.update(overrides)
        return OpenStackProvider(**base)

    def test_blank_password_clears_prior_driver(self):
        connector = OpenStackConnector()
        fake_driver = MagicMock(name="driver-userA")
        with (
            patch(
                "swmcloudgate.routers.openstack.connector.load_openstack_provider",
                return_value=self._provider(),
            ),
            patch(
                "swmcloudgate.routers.openstack.connector.get_driver",
                return_value=MagicMock(return_value=fake_driver),
            ),
        ):
            connector.reinitialize("userA", "passA", "compute")
            self.assertIs(connector._driver, fake_driver)

            with self.assertRaises(OpenStackAuthError):
                connector.reinitialize("userA", "", "compute")
            self.assertIsNone(connector._driver)

    def test_missing_creds_clear_driver(self):
        connector = OpenStackConnector()
        fake_driver = MagicMock(name="driver")
        with (
            patch(
                "swmcloudgate.routers.openstack.connector.load_openstack_provider",
                return_value=self._provider(),
            ),
            patch(
                "swmcloudgate.routers.openstack.connector.get_driver",
                return_value=MagicMock(return_value=fake_driver),
            ),
        ):
            connector.reinitialize("userA", "passA", "compute")
            with self.assertRaises(OpenStackAuthError):
                connector.reinitialize(None, None, "compute")
            self.assertIsNone(connector._driver)

    def test_http_auth_url_rejected_by_default(self):
        connector = OpenStackConnector()
        with patch(
            "swmcloudgate.routers.openstack.connector.load_openstack_provider",
            return_value=self._provider(auth_url="http://keystone.test:5000"),
        ):
            with self.assertRaises(OpenStackAuthError) as ctx:
                connector.reinitialize("userA", "passA", "compute")
            self.assertIn("HTTPS", str(ctx.exception))
            self.assertIsNone(connector._driver)

    def test_https_enables_ssl_verify(self):
        connector = OpenStackConnector()
        fake_driver = MagicMock()
        libcloud.security.VERIFY_SSL_CERT = False
        with (
            patch(
                "swmcloudgate.routers.openstack.connector.load_openstack_provider",
                return_value=self._provider(verify_ssl=True),
            ),
            patch(
                "swmcloudgate.routers.openstack.connector.get_driver",
                return_value=MagicMock(return_value=fake_driver),
            ),
        ):
            connector.reinitialize("userA", "passA", "compute")
        self.assertTrue(libcloud.security.VERIFY_SSL_CERT)
        self.assertIs(connector._driver, fake_driver)

    def test_mock_mode_validates_creds_without_driver(self):
        os.environ["SWM_TEST_CONFIG"] = "test/data/responses.json"
        connector = OpenStackConnector()
        connector.reinitialize("demo1", "demo1", "compute")
        self.assertIsNone(connector._driver)
        with self.assertRaises(OpenStackAuthError):
            connector.reinitialize("demo1", "", "compute")
        self.assertIsNone(connector._driver)


class TestOpenStackAuthHttp(unittest.TestCase):
    def setUp(self):
        get_settings.cache_clear()
        self._env = os.environ.copy()
        os.environ["SWM_TEST_CONFIG"] = "test/data/responses.json"
        # Empty OpenStack user/pass so username-only headers cannot fall back.
        os.environ["SWM_GATE_CONFIG"] = "test/data/cloud-gate-openstack-empty.yaml"
        get_settings.cache_clear()
        from swmcloudgate.main import app

        self.client = TestClient(app)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        get_settings.cache_clear()

    def test_flavors_without_password_returns_401(self):
        resp = self.client.get(
            "/openstack/flavors",
            headers={"Accept": "application/json", "username": "demo1"},
        )
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
