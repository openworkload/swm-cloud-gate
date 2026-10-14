import os
import json
import unittest

from swmcloudgate.routers.azure.connector import (
    IS_MAIN_PLACEHOLDER,
    HOST_NAME_PLACEHOLDER,
    STORAGE_KEY_B64_PLACEHOLDER,
    CONTAINER_REGISTRY_PASSWORD_B64_PLACEHOLDER,
    MAIN_INSTANCE_HOSTNAME_PLACEHOLDER,
    MAIN_INSTANCE_PRIVATE_IP_PLACEHOLDER,
    AzureConnector,
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

    def _render_cloud_init_script(self, install_checkpoint_tools: bool = False):
        return self.connector._get_cloud_init_script(
            job_id="job-1",
            container_image="registry.example.org/image:tag",
            container_registry="registry.example.org",
            container_registry_username="user",
            storage_account="storageaccount",
            storage_container="storagecontainer",
            runtime_params={"swm_source": "ssh"},
            user_ssh_cert="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC== user@example",
            install_checkpoint_tools=install_checkpoint_tools,
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
        self.assertIn(f'azure_storage_key_b64="{STORAGE_KEY_B64_PLACEHOLDER}"', cloud_init_script)
        self.assertIn("azure_storage_key=$(printf '%s' \"$azure_storage_key_b64\" | base64 -d)", cloud_init_script)
        self.assertIn(
            f'container_registry_password_b64="{CONTAINER_REGISTRY_PASSWORD_B64_PLACEHOLDER}"',
            cloud_init_script,
        )
        self.assertIn(
            "container_registry_password=$(printf '%s' \"$container_registry_password_b64\" | base64 -d)",
            cloud_init_script,
        )
        self.assertNotIn("user<&>\"'pass", cloud_init_script)
        self.assertIn("--password-stdin", cloud_init_script)
        self.assertIn(
            'podman login "$container_registry"',
            cloud_init_script,
        )
        self.assertNotIn('--password "$container_registry_password"', cloud_init_script)
        self.assertNotIn(
            "podman login registry.example.org --username user --password user<&>\"'pass",
            cloud_init_script,
        )
        self.assertIn(
            "ensure_root_authorized_key 'ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC== user@example'",
            cloud_init_script,
        )
        self.assertIn("setup_passwordless_root_ssh", cloud_init_script)
        self.assertIn("PermitRootLogin prohibit-password", cloud_init_script)
        self.assertIn("/home/.swm/cluster_root.pub", cloud_init_script)
        self.assertNotIn("&lt;", cloud_init_script)
        self.assertNotIn("&gt;", cloud_init_script)
        self.assertNotIn("&amp;", cloud_init_script)
        self.assertNotIn("getent hosts", cloud_init_script)
        self.assertIn("setup_log_symlinks", cloud_init_script)
        self.assertIn('local swm_log_dir="/opt/swm/spool/${HOST_NAME}@${domain}/log"', cloud_init_script)
        self.assertIn('local job_dir="/opt/swm/spool/job/job-1"', cloud_init_script)
        self.assertIn('ln -s "$swm_log_dir" /var/log/swm', cloud_init_script)
        self.assertIn('ln -s "$job_dir" /var/log/job', cloud_init_script)
        self.assertIn("install_mana_dmtcp", cloud_init_script)
        self.assertIn("checkpoint tools not requested -- skip MANA/DMTCP install", cloud_init_script)

    def test_cloud_init_installs_mana_when_checkpoint_requested(self):
        cloud_init_script = self._render_cloud_init_script(install_checkpoint_tools=True)
        self.assertIn("install_mana_dmtcp", cloud_init_script)
        self.assertIn("install_checkpoint_tools=true", cloud_init_script)
        self.assertIn("https://github.com/mpickpt/mana.git", cloud_init_script)
        self.assertIn("mana_prefix=/opt/mana", cloud_init_script)

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
        self.assertIn("base64(parameters('storageKey'))", custom_data)
        self.assertIn("base64(parameters('containerRegistryPassword'))", custom_data)
        self.assertIn(f"'{CONTAINER_REGISTRY_PASSWORD_B64_PLACEHOLDER}'", custom_data)

    def test_partition_json_marks_registry_password_securestring(self):
        template = self._load_template()
        self.assertEqual(
            template["parameters"]["containerRegistryPassword"]["type"],
            "securestring",
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
        self.assertIn("base64(parameters('storageKey'))", custom_data)
        self.assertIn("base64(parameters('containerRegistryPassword'))", custom_data)
        self.assertIn(
            "[resourceId('Microsoft.Network/networkInterfaces', variables('networkInterfaceName'))]",
            compute_vm["dependsOn"],
        )
