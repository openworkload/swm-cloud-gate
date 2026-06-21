import json
import os
import unittest
from unittest.mock import Mock

from swmcloudgate.routers.azure.connector import AzureConnector, MAX_VM_COUNT


class TestAzureConnectorMultiNode(unittest.TestCase):
    def setUp(self):
        os.environ["SWM_TEST_CONFIG"] = "test/data/responses.json"
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
            storage_container="storagecontainer",
            runtime_params={"swm_source": "ssh"},
            user_ssh_cert="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC",
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

    def test_compute_vm_dependencies_include_main_and_compute_nics(self):
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
        self.assertIn('timeout 2 bash -c "</dev/tcp/${MAIN_INSTANCE_PRIVATE_IP}/2049"', cloud_init_script)
        self.assertIn("local count=0", cloud_init_script)
        self.assertIn("local max_mount_attempts=60", cloud_init_script)
        self.assertNotIn('systemctl restart docker # fix rare "connection closed" issues', cloud_init_script)
        self.assertNotIn("getent hosts", cloud_init_script)
        self.assertIn('echo "$(date): could not determine main instance details" >&2', cloud_init_script)

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

        result, resource_group_name = self.connector.create_deployment(
            job_id="job-1",
            partition_name="part1",
            os_version="ubuntu-hpc/2204",
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
        self.assertNotIn("storagekey", parameters["cloudInitScript"]["value"])
        self.assertEqual(
            template["variables"]["linuxConfiguration"]["ssh"]["publicKeys"][0]["path"],
            "[format('/home/{0}/.ssh/authorized_keys', parameters('adminUsername'))]",
        )

        main_vm = next(resource for resource in virtual_machines if resource["name"] == "[parameters('vmNameMain')]")
        self.assertIn("parameters('storageKey')", main_vm["properties"]["osProfile"]["customData"])

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
                os_version="ubuntu-hpc/2204",
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
            )

        self.connector._resource_client.resource_groups.begin_delete.assert_called_once_with("part1-resource-group")
        delete_operation.wait.assert_called_once()
