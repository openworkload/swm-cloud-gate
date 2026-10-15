"""job_id validation and shell-safe cloud-init / Heat rendering (issue 28)."""

from __future__ import annotations

import os
import shlex
import unittest
from unittest.mock import Mock

from swmcloudgate.validation import assert_job_id
from swmcloudgate.routers.azure.connector import AzureConnector
from swmcloudgate.routers.openstack.connector import OpenStackConnector

VALID_JOB_ID = "40565124-9c03-11ee-8ca4-a3132f7ae2fb"


class TestAssertJobId(unittest.TestCase):
    def test_accepts_uuid(self) -> None:
        self.assertEqual(assert_job_id(VALID_JOB_ID), VALID_JOB_ID)
        self.assertEqual(assert_job_id(VALID_JOB_ID.upper()), VALID_JOB_ID.upper())

    def test_rejects_injection_and_garbage(self) -> None:
        for bad in ("$(id)", "abc; rm -rf /", "has space", "a\nb", "../x", "job-1", "", None):
            with self.assertRaises(ValueError):
                assert_job_id(bad)


class TestAzureJobIdInCloudInit(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["SWM_TEST_CONFIG"] = "test/data/responses.json"
        self.connector = AzureConnector()

    def tearDown(self) -> None:
        os.environ.pop("SWM_TEST_CONFIG", None)

    def test_create_deployment_rejects_malicious_job_id(self) -> None:
        self.connector._test_responses = {}
        self.connector._subscription_id = "test-subscription"
        self.connector._resource_client = Mock()
        with self.assertRaises(ValueError) as ctx:
            self.connector.create_deployment(
                job_id="$(id)",
                partition_name="part1",
                os_version="ubuntu-hpc/2404",
                container_image="registry.example.org/image:tag",
                container_registry_username="",
                container_registry_password="",
                storage_account="storageaccount",
                storage_key="storagekey",
                storage_container="storagecontainer",
                flavor_name="Standard_B2s",
                username="azureuser",
                count="1",
                runtime="swm_source=ssh",
                location="eastus",
                ports="10001",
                user_ssh_cert="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC",
                allow_ssh_from_internet=True,
            )
        self.assertIn("job_id must be a UUID", str(ctx.exception))
        self.connector._resource_client.resource_groups.create_or_update.assert_not_called()

    def test_cloud_init_job_dir_uses_shellquote(self) -> None:
        script = self.connector._get_cloud_init_script(
            job_id=VALID_JOB_ID,
            container_image="registry.example.org/image:tag",
            container_registry="registry.example.org",
            container_registry_username="user",
            storage_account="storageaccount",
            storage_container="storagecontainer",
            runtime_params={"swm_source": "ssh"},
            user_ssh_cert="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC",
        )
        quoted = shlex.quote(VALID_JOB_ID)
        self.assertIn(f"local job_dir=/opt/swm/spool/job/{quoted}", script)
        self.assertNotIn('local job_dir="/opt/swm/spool/job/$(', script)


class TestOpenStackCloudInitEscaping(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["SWM_TEST_CONFIG"] = "test/data/responses.json"
        self.connector = OpenStackConnector()

    def tearDown(self) -> None:
        os.environ.pop("SWM_TEST_CONFIG", None)

    def test_create_stack_rejects_malicious_job_id(self) -> None:
        self.connector._test_responses = {"stacks": []}
        with self.assertRaises(ValueError):
            self.connector.create_stack(
                "tenant",
                "swm-part",
                "image",
                "flavor",
                "key",
                "1",
                "$(id)",
                "swm_source=ssh",
                "10001",
                "quay.io/example/image:tag",
            )

    def test_cloud_init_quotes_job_id_and_image(self) -> None:
        image = "quay.io/example/image:tag&variant=1"
        script = self.connector._get_cloud_init_script(
            VALID_JOB_ID,
            "swm_source=ssh,ssh_pub_key=ssh-rsa AAAAB3",
            image,
        )
        self.assertIn(f"local job_dir=/opt/swm/spool/job/{shlex.quote(VALID_JOB_ID)}", script)
        self.assertIn(f"podman pull {shlex.quote(image)}", script)
        self.assertNotIn("&amp;", script)

    def test_heat_stack_uses_yaml_safe_strings_not_html(self) -> None:
        template = self.connector._get_stack_template(
            stack_name='stack"name',
            image_name="ubuntu & friends",
            flavor_name="m1.small",
            key_name="mykey",
            count="1",
            job_id=VALID_JOB_ID,
            runtime="swm_source=ssh",
            ports="10001,10022",
            container_image="quay.io/example/image:tag",
        )
        # yaml.safe_load already parsed; ensure values survived without HTML entities
        self.assertEqual(template["stack_name"], 'stack"name')
        self.assertEqual(template["template"]["parameters"]["image"]["default"], "ubuntu & friends")
        self.assertNotIn("&amp;", str(template))
        self.assertNotIn("&#34;", str(template))


if __name__ == "__main__":
    unittest.main()
