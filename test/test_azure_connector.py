import os
import json
import unittest
from unittest.mock import Mock

from swmcloudgate.routers.azure.connector import (
    MAX_VM_COUNT,
    CONTAINER_REGISTRY_PASSWORD_B64_PLACEHOLDER,
    AzureConnector,
    image_registry_host,
    assert_registry_credentials_safe,
)


class TestAzureConnectorMultiNode(unittest.TestCase):
    def setUp(self):
        os.environ["SWM_TEST_CONFIG"] = "test/data/responses.json"
        self.connector = AzureConnector()

    def tearDown(self):
        os.environ.pop("SWM_TEST_CONFIG", None)

    def _load_template(self):
        with open("swmcloudgate/routers/azure/templates/partition.json") as template_file:
            return json.load(template_file)

    def _render_cloud_init_script(self, **overrides):
        params = {
            "job_id": "job-1",
            "container_image": "registry.example.org/image:tag",
            "container_registry": "registry.example.org",
            "container_registry_username": "user",
            "storage_account": "storageaccount",
            "storage_container": "storagecontainer",
            "runtime_params": {"swm_source": "ssh"},
            "user_ssh_cert": "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC",
        }
        params.update(overrides)
        return self.connector._get_cloud_init_script(
            job_id=params["job_id"],
            container_image=params["container_image"],
            container_registry=params["container_registry"],
            container_registry_username=params["container_registry_username"],
            storage_account=params["storage_account"],
            storage_container=params["storage_container"],
            runtime_params=params["runtime_params"],
            user_ssh_cert=params["user_ssh_cert"],
        )

    def test_parse_vm_count_defaults_to_one_for_missing(self):
        self.assertEqual(self.connector._parse_vm_count(None), 1)
        self.assertEqual(self.connector._parse_vm_count(""), 1)

    def test_parse_vm_count_rejects_non_integer(self):
        with self.assertRaises(ValueError):
            self.connector._parse_vm_count("abc")

    def test_parse_vm_count_rejects_out_of_range_values(self):
        with self.assertRaises(ValueError):
            self.connector._parse_vm_count("0")
        with self.assertRaises(ValueError):
            self.connector._parse_vm_count(str(MAX_VM_COUNT + 1))

    def test_validate_admin_username_accepts_linux_compatible_names(self):
        self.connector._validate_admin_username("taras")
        self.connector._validate_admin_username("a")
        self.connector._validate_admin_username("user_name-1")

    def test_validate_admin_username_rejects_invalid_names(self):
        for username in ("", "Taras", "1user", "user.name", "a" * 33):
            with self.assertRaises(ValueError):
                self.connector._validate_admin_username(username)

    def test_add_compute_vms_keeps_single_vm_template_unchanged(self):
        template = self._load_template()
        original_resource_count = len(template["resources"])

        self.connector._add_compute_vms("part1", 1, template)

        self.assertEqual(len(template["resources"]), original_resource_count)

    def test_add_compute_vms_adds_nics_vms_and_extensions(self):
        template = self._load_template()

        self.connector._add_compute_vms("part1", 3, template)

        network_interfaces = [
            resource for resource in template["resources"] if resource["type"] == "Microsoft.Network/networkInterfaces"
        ]
        virtual_machines = [
            resource for resource in template["resources"] if resource["type"] == "Microsoft.Compute/virtualMachines"
        ]
        extensions = [
            resource
            for resource in template["resources"]
            if resource["type"] == "Microsoft.Compute/virtualMachines/extensions"
        ]

        self.assertEqual(len(network_interfaces), 3)
        self.assertEqual(len(virtual_machines), 3)
        self.assertEqual(len(extensions), 3)

    def test_compute_nics_do_not_have_public_ip(self):
        template = self._load_template()

        self.connector._add_compute_vms("part1", 2, template)

        compute_nic = next(
            resource
            for resource in template["resources"]
            if resource["type"] == "Microsoft.Network/networkInterfaces"
            and resource["name"] == "[format('part1-compute1-NetInt')]"
        )
        nic_properties = compute_nic["properties"]["ipConfigurations"][0]["properties"]
        self.assertNotIn("publicIPAddress", nic_properties)

    def test_compute_vm_preserves_main_nic_dependency_and_adds_compute_nic(self):
        template = self._load_template()

        self.connector._add_compute_vms("part1", 2, template)

        compute_vm = next(
            resource
            for resource in template["resources"]
            if resource["type"] == "Microsoft.Compute/virtualMachines"
            and resource["name"] == "[format('part1-compute1')]"
        )
        self.assertIn(
            "[resourceId('Microsoft.Network/networkInterfaces', 'part1-compute1-NetInt')]",
            compute_vm["dependsOn"],
        )
        self.assertIn(
            "[resourceId('Microsoft.Network/networkInterfaces', variables('networkInterfaceName'))]",
            compute_vm["dependsOn"],
        )

    def test_compute_nic_dependencies_preserve_non_public_ip_dependencies(self):
        template = self._load_template()

        self.connector._add_compute_vms("part1", 2, template)

        compute_nic = next(
            resource
            for resource in template["resources"]
            if resource["type"] == "Microsoft.Network/networkInterfaces"
            and resource["name"] == "[format('part1-compute1-NetInt')]"
        )
        self.assertIn(
            "[resourceId('Microsoft.Network/networkSecurityGroups', parameters('networkSecurityGroupName'))]",
            compute_nic["dependsOn"],
        )
        self.assertIn(
            "[resourceId('Microsoft.Network/virtualNetworks/subnets', parameters('virtualNetworkName'), "
            "parameters('subnetName'))]",
            compute_nic["dependsOn"],
        )
        self.assertNotIn(
            "[resourceId('Microsoft.Network/publicIPAddresses', variables('publicIPAddressName'))]",
            compute_nic["dependsOn"],
        )

    def test_compute_vm_extension_is_duplicated_for_compute_nodes(self):
        template = self._load_template()

        self.connector._add_compute_vms("part1", 2, template)

        compute_extension = next(
            resource
            for resource in template["resources"]
            if resource["type"] == "Microsoft.Compute/virtualMachines/extensions"
            and resource["name"] == "[format('part1-compute1/{0}', variables('extensionName'))]"
        )
        self.assertIn(
            "[resourceId('Microsoft.Compute/virtualMachines', 'part1-compute1')]",
            compute_extension["dependsOn"],
        )
        self.assertNotIn(
            "[resourceId('Microsoft.Compute/virtualMachines', parameters('vmNameMain'))]",
            compute_extension["dependsOn"],
        )

    def test_cloud_init_script_detects_main_and_compute_vm_roles(self):
        cloud_init_script = self._render_cloud_init_script()

        self.assertIn('HOST_NAME="__SWM_HOST_NAME__"', cloud_init_script)
        self.assertIn("IS_MAIN=__SWM_IS_MAIN__", cloud_init_script)
        self.assertIn('MAIN_INSTANCE_HOSTNAME="__SWM_MAIN_INSTANCE_HOSTNAME__"', cloud_init_script)

    def test_cloud_init_script_configures_nfs_for_shared_home_mount(self):
        cloud_init_script = self._render_cloud_init_script()

        self.assertIn("exportfs -ra", cloud_init_script)
        self.assertIn("systemctl enable nfs-kernel-server", cloud_init_script)
        self.assertIn('echo "$MAIN_INSTANCE_PRIVATE_IP:/home /home nfs', cloud_init_script)
        self.assertIn('echo "$MAIN_INSTANCE_PRIVATE_IP:$SWM_ROOT $SWM_ROOT nfs', cloud_init_script)
        self.assertIn(
            'echo "$SWM_ROOT $PRIVATE_SUBNET_CIDR(rw,async,no_root_squash,no_subtree_check)"',
            cloud_init_script,
        )
        self.assertIn("wait_for_shared_swm_root", cloud_init_script)
        self.assertIn('mountpoint -q "$SWM_ROOT"', cloud_init_script)
        self.assertIn("compute node uses NFS-shared", cloud_init_script)
        self.assertIn("--job-node main", cloud_init_script)
        self.assertIn("--job-node compute", cloud_init_script)
        self.assertIn('--parent-host "$MAIN_INSTANCE_HOSTNAME"', cloud_init_script)
        self.assertIn("parent_host=$MAIN_INSTANCE_HOSTNAME", cloud_init_script)
        self.assertIn("parent_port=10001", cloud_init_script)
        self.assertIn("parent_host=localhost", cloud_init_script)
        self.assertIn("parent_port=10002", cloud_init_script)
        self.assertIn("SWM_PARENT_HOST=$parent_host", cloud_init_script)
        self.assertIn("SWM_PARENT_PORT=$parent_port", cloud_init_script)
        self.assertIn("/etc/systemd/system/swm.service.d/parent.conf", cloud_init_script)
        self.assertIn("systemctl daemon-reload", cloud_init_script)
        self.assertIn('timeout 2 bash -c "</dev/tcp/${MAIN_INSTANCE_PRIVATE_IP}/2049"', cloud_init_script)
        self.assertIn("local count=0", cloud_init_script)
        self.assertIn("local max_mount_attempts=60", cloud_init_script)
        self.assertNotIn('systemctl restart docker # fix rare "connection closed" issues', cloud_init_script)
        self.assertNotIn("getent hosts", cloud_init_script)
        self.assertIn('echo "$(date): could not determine main instance details" >&2', cloud_init_script)

    def test_cloud_init_script_uses_registry_password_placeholder(self):
        cloud_init_script = self._render_cloud_init_script()

        self.assertIn(
            f'container_registry_password_b64="{CONTAINER_REGISTRY_PASSWORD_B64_PLACEHOLDER}"',
            cloud_init_script,
        )
        self.assertIn(
            "container_registry_password=$(printf '%s' \"$container_registry_password_b64\" | base64 -d)",
            cloud_init_script,
        )
        self.assertIn('if [ -n "$container_registry_password" ]; then', cloud_init_script)
        self.assertIn("--password-stdin", cloud_init_script)
        self.assertIn(
            'podman login "$container_registry"',
            cloud_init_script,
        )
        self.assertNotIn('--password "$container_registry_password"', cloud_init_script)
        self.assertIn('podman pull "$container_image"', cloud_init_script)
        self.assertNotIn("pa&ss<word>", cloud_init_script)

    def test_create_deployment_builds_multi_node_template(self):
        self.connector._test_responses = {}
        self.connector._subscription_id = "test-subscription"
        self.connector._resource_client = Mock()
        self.connector._resource_client.resource_groups.create_or_update.return_value = Mock(
            id="/subscriptions/test/rg"
        )

        deployment_result = {"id": "/subscriptions/test/deployments/part1"}
        deployment_operation = Mock()
        deployment_operation.result.return_value = deployment_result
        self.connector._resource_client.deployments.begin_create_or_update.return_value = deployment_operation

        acr_password = "acr-secret-TOKEN-xyz"
        result, resource_group_name = self.connector.create_deployment(
            job_id="job-1",
            partition_name="part1",
            os_version="ubuntu-hpc/2404",
            container_image="registry.example.org/image:tag",
            container_registry_username="user",
            container_registry_password=acr_password,
            storage_account="storageaccount",
            storage_key="storagekey",
            storage_container="storagecontainer",
            flavor_name="Standard_B2s",
            username="azureuser",
            count="3",
            runtime="swm_source=ssh",
            location="eastus",
            ports="10001,10022",
            user_ssh_cert="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC",
            container_registry_server="registry.example.org",
        )

        self.assertEqual(result, deployment_result)
        self.assertEqual(resource_group_name, "part1-resource-group")
        _, _, deployment_properties = self.connector._resource_client.deployments.begin_create_or_update.call_args[0]
        template = deployment_properties["properties"]["template"]
        parameters = deployment_properties["properties"]["parameters"]
        virtual_machines = [r for r in template["resources"] if r["type"] == "Microsoft.Compute/virtualMachines"]

        self.assertEqual(len(virtual_machines), 3)
        self.assertEqual(parameters["vmNameMain"]["value"], "part1-main")
        self.assertEqual(parameters["storageKey"]["value"], "storagekey")
        self.assertEqual(parameters["containerRegistryPassword"]["value"], acr_password)
        self.assertNotIn("storagekey", parameters["cloudInitScript"]["value"])
        self.assertNotIn(acr_password, parameters["cloudInitScript"]["value"])
        self.assertIn(CONTAINER_REGISTRY_PASSWORD_B64_PLACEHOLDER, parameters["cloudInitScript"]["value"])
        self.assertEqual(
            template["variables"]["linuxConfiguration"]["ssh"]["publicKeys"][0]["path"],
            "[concat('/home/', parameters('adminUsername'), '/.ssh/authorized_keys')]",
        )

        main_vm = next(resource for resource in virtual_machines if resource["name"] == "[parameters('vmNameMain')]")
        self.assertIn("base64(parameters('storageKey'))", main_vm["properties"]["osProfile"]["customData"])
        self.assertIn(
            "base64(parameters('containerRegistryPassword'))",
            main_vm["properties"]["osProfile"]["customData"],
        )

    def test_create_deployment_rolls_back_resource_group_on_failure(self):
        self.connector._test_responses = {}
        self.connector._subscription_id = "test-subscription"
        self.connector._resource_client = Mock()
        self.connector._resource_client.resource_groups.create_or_update.return_value = Mock(
            id="/subscriptions/test/rg"
        )

        deployment_operation = Mock()
        deployment_operation.result.side_effect = RuntimeError("deployment failed")
        self.connector._resource_client.deployments.begin_create_or_update.return_value = deployment_operation
        delete_operation = Mock()
        self.connector._resource_client.resource_groups.begin_delete.return_value = delete_operation

        with self.assertRaises(RuntimeError):
            self.connector.create_deployment(
                job_id="job-1",
                partition_name="part1",
                os_version="ubuntu-hpc/2404",
                container_image="registry.example.org/image:tag",
                container_registry_username="user",
                container_registry_password="pass",
                storage_account="storageaccount",
                storage_key="storagekey",
                storage_container="storagecontainer",
                flavor_name="Standard_B2s",
                username="azureuser",
                count="3",
                runtime="swm_source=ssh",
                location="eastus",
                ports="10001,10022",
                user_ssh_cert="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC",
                container_registry_server="registry.example.org",
            )

        self.connector._resource_client.resource_groups.begin_delete.assert_called_once_with("part1-resource-group")
        delete_operation.result.assert_called_once()

    def test_deployment_properties_debug_log_redacts_secrets(self):
        acr_password = "acr-secret-TOKEN-for-log-test"
        cloud_init = self._render_cloud_init_script()
        with self.assertLogs("swm", level="DEBUG") as captured:
            props = self.connector._get_deployment_properties(
                job_id="job-log",
                partition_name="part-log",
                flavor_name="Standard_B2s",
                os_version="ubuntu-hpc/2404",
                username="azureuser",
                user_pub_key="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC",
                storage_key="storagekey-secret",
                container_registry_password=acr_password,
                cloud_init_script=cloud_init,
                ports="10001",
                vm_count=1,
            )
        log_text = "\n".join(captured.output)
        self.assertNotIn(acr_password, log_text)
        self.assertNotIn("storagekey-secret", log_text)
        self.assertNotIn(cloud_init[:80], log_text)
        parameters = props["properties"]["parameters"]
        self.assertEqual(parameters["containerRegistryPassword"]["value"], acr_password)
        self.assertNotIn(acr_password, parameters["cloudInitScript"]["value"])


class TestRegistryHostAllowlist(unittest.TestCase):
    def test_image_registry_host_parses_common_forms(self):
        self.assertEqual(image_registry_host("swmregistry.azurecr.io/ns/img:tag"), "swmregistry.azurecr.io")
        self.assertEqual(image_registry_host("Registry.Example.ORG/image:tag"), "registry.example.org")
        self.assertEqual(image_registry_host("localhost:5000/foo:bar"), "localhost:5000")
        self.assertIsNone(image_registry_host("ubuntu:24.04"))
        self.assertIsNone(image_registry_host("library/ubuntu:24.04"))
        self.assertIsNone(image_registry_host(""))

    def test_assert_registry_credentials_safe_allows_matching_host(self):
        assert_registry_credentials_safe(
            "registry.example.org/image:tag",
            "registry.example.org",
            "user",
            "secret",
        )

    def test_assert_registry_credentials_safe_rejects_foreign_host(self):
        with self.assertRaises(ValueError) as ctx:
            assert_registry_credentials_safe(
                "evil.example/image:tag",
                "registry.example.org",
                "user",
                "secret",
            )
        self.assertIn("registry.example.org", str(ctx.exception))
        self.assertNotIn("secret", str(ctx.exception))

    def test_assert_registry_credentials_safe_requires_server_when_creds_set(self):
        with self.assertRaises(ValueError) as ctx:
            assert_registry_credentials_safe(
                "registry.example.org/image:tag",
                "",
                "user",
                "secret",
            )
        self.assertIn("server is required", str(ctx.exception))

    def test_assert_registry_credentials_safe_allows_any_image_without_creds(self):
        assert_registry_credentials_safe("evil.example/image:tag", "", "", "")
        assert_registry_credentials_safe("ubuntu:24.04", "registry.example.org", "", "")

    def test_create_deployment_rejects_foreign_registry_when_creds_set(self):
        connector = AzureConnector()
        connector._test_responses = {}
        connector._subscription_id = "test-subscription"
        connector._resource_client = Mock()
        with self.assertRaises(ValueError):
            connector.create_deployment(
                job_id="job-1",
                partition_name="part1",
                os_version="ubuntu-hpc/2404",
                container_image="evil.example/image:tag",
                container_registry_username="user",
                container_registry_password="secret",
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
                container_registry_server="registry.example.org",
            )
        connector._resource_client.resource_groups.create_or_update.assert_not_called()
