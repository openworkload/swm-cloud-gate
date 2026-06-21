import json
import os
import unittest

from swmcloudgate.routers.azure.connector import (
    AzureConnector,
    HOST_NAME_PLACEHOLDER,
    IS_MAIN_PLACEHOLDER,
    MAIN_INSTANCE_HOSTNAME_PLACEHOLDER,
    MAIN_INSTANCE_PRIVATE_IP_PLACEHOLDER,
)


class TestAzureConnectorCustomDataInjection(unittest.TestCase):
    _test_config = "test/data/responses.json"

    def setUp(self):
        os.environ["SWM_TEST_CONFIG"] = self._test_config
        self.connector = AzureConnector()

    def tearDown(self):
        os.environ.pop("SWM_TEST_CONFIG", None)

    def _load_template(self):
        with open("swmcloudgate/routers/azure/templates/partition.json") as template_file:
            return json.load(template_file)

    def _render_cloud_init_script(self):
        return self.connector._get_cloud_init_script(
            job_id="job-1",
            container_image="registry.example.org/image:tag",
            container_registry="registry.example.org",
            container_registry_username="user",
            container_registry_password="pass",
            storage_account="storageaccount",
            storage_key="storagekey",
            storage_container="storagecontainer",
            runtime_params={"swm_source": "ssh"},
            user_ssh_cert="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC",
        )

    def test_cloud_init_script_uses_explicit_main_instance_placeholders(self):
        cloud_init_script = self._render_cloud_init_script()

        self.assertIn(f'HOST_NAME="{HOST_NAME_PLACEHOLDER}"', cloud_init_script)
        self.assertIn(f"IS_MAIN={IS_MAIN_PLACEHOLDER}", cloud_init_script)
        self.assertIn(
            f'MAIN_INSTANCE_HOSTNAME="{MAIN_INSTANCE_HOSTNAME_PLACEHOLDER}"',
            cloud_init_script,
        )
        self.assertIn(
            f'MAIN_INSTANCE_PRIVATE_IP="{MAIN_INSTANCE_PRIVATE_IP_PLACEHOLDER}"',
            cloud_init_script,
        )
        self.assertNotIn("getent hosts", cloud_init_script)

    def test_main_vm_custom_data_replaces_placeholders_via_arm(self):
        template = self._load_template()

        self.connector._configure_main_vm_custom_data(template)

        main_vm = next(
            resource
            for resource in template["resources"]
            if resource["type"] == "Microsoft.Compute/virtualMachines"
            and resource["name"] == "[parameters('vmNameMain')]"
        )
        custom_data = main_vm["properties"]["osProfile"]["customData"]
        self.assertIn("[base64(", custom_data)
        self.assertIn(f"'{HOST_NAME_PLACEHOLDER}'", custom_data)
        self.assertIn("parameters('vmNameMain')", custom_data)
        self.assertIn(f"'{IS_MAIN_PLACEHOLDER}'", custom_data)
        self.assertIn("'true'", custom_data)
        self.assertIn(f"'{MAIN_INSTANCE_PRIVATE_IP_PLACEHOLDER}'", custom_data)
        self.assertIn(
            "reference(resourceId('Microsoft.Network/networkInterfaces'",
            custom_data,
        )

    def test_compute_vm_custom_data_uses_explicit_main_private_ip_reference(self):
        template = self._load_template()

        self.connector._configure_main_vm_custom_data(template)
        self.connector._add_compute_vms("part1", 2, template)

        compute_vm = next(
            resource
            for resource in template["resources"]
            if resource["type"] == "Microsoft.Compute/virtualMachines"
            and resource["name"] == "[format('part1-compute1')]"
        )
        custom_data = compute_vm["properties"]["osProfile"]["customData"]
        self.assertIn(f"'{HOST_NAME_PLACEHOLDER}'", custom_data)
        self.assertIn("'part1-compute1'", custom_data)
        self.assertIn(f"'{IS_MAIN_PLACEHOLDER}'", custom_data)
        self.assertIn("'false'", custom_data)
        self.assertIn(f"'{MAIN_INSTANCE_HOSTNAME_PLACEHOLDER}'", custom_data)
        self.assertIn("parameters('vmNameMain')", custom_data)
        self.assertIn(f"'{MAIN_INSTANCE_PRIVATE_IP_PLACEHOLDER}'", custom_data)
        self.assertIn(
            "reference(resourceId('Microsoft.Network/networkInterfaces'",
            custom_data,
        )
        self.assertIn(
            "[resourceId('Microsoft.Network/networkInterfaces', variables('networkInterfaceName'))]",
            compute_vm["dependsOn"],
        )
