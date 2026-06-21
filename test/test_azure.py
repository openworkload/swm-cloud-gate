import os
import socket
import asyncio
import unittest
import json
from multiprocessing import Process

import aiohttp
import uvicorn
import asynctest

from swmcloudgate.routers.azure.connector import AzureConnector, MAX_VM_COUNT


class TestAzureGate(asynctest.TestCase):

    _hostname: str = socket.gethostname()
    _port: int = 8445
    _default_headers = {
        "Accept": "application/json",
        "subscriptionid": "test",
        "tenantid": "test",
        "appid": "test",
        "extra": "location=test",
    }

    async def setUp(self):
        self.maxDiff = None
        os.environ["SWM_TEST_CONFIG"] = "test/data/responses.json"
        # Point routers at a test cloud-gate.yaml that provides non-empty
        # subscription/tenant/app IDs so the credential guards in the Azure
        # routes don't short-circuit with "No subscription ID" etc. The
        # connector also short-circuits real Azure calls when SWM_TEST_CONFIG
        # is set, so the config values are only used for those presence checks.
        os.environ["SWM_GATE_CONFIG"] = "test/data/cloud-gate.yaml"
        self.proc = Process(
            target=uvicorn.run,
            args=("swmcloudgate.main:app",),
            kwargs={
                "host": self._hostname,
                "port": self._port,
                "log_config": "swmcloudgate/logging.yaml",
                "reload": False,
                "timeout_keep_alive": 60,
            },
            daemon=True,
        )
        self.proc.start()
        await asyncio.sleep(0.5)  # time for the server to start
        self.assertTrue(self.proc.is_alive())

    async def tearDown(self):
        self.assertTrue(self.proc.is_alive())
        self.proc.terminate()

    async def test_list_flavors(self):
        async with aiohttp.ClientSession(headers=self._default_headers) as session:
            async with session.get(
                url=f"http://{self._hostname}:{self._port}/azure/flavors",
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "flavors": [
                    {
                        "cpus": 2,
                        "gpus": 0,
                        "id": "9348abe1-2a12-4ba7-9942-920a58fa887f",
                        "mem": 1073,
                        "name": "flavor1",
                        "price": 3.0,
                        "storage": 12884,
                    },
                    {
                        "cpus": 8,
                        "gpus": 0,
                        "id": "5acfa3a8-991b-4e5e-822b-3fadbfc93f9a",
                        "mem": 2147,
                        "name": "flavor2",
                        "price": 8.0,
                        "storage": 154618,
                    },
                ]
            },
        )

    async def test_list_partitions(self):
        async with aiohttp.ClientSession(headers=self._default_headers) as session:
            async with session.get(
                url=f"http://{self._hostname}:{self._port}/azure/partitions",
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "partitions": [
                    {
                        "compute_instances_ips": [],
                        "created": None,
                        "description": None,
                        "id": "/subscriptions/3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75/resourceGroups/rg1-resource-group",
                        "master_private_ip": "",
                        "master_public_ip": "",
                        "name": "rg1",
                        "status": None,
                        "updated": None,
                    },
                    {
                        "compute_instances_ips": [],
                        "created": None,
                        "description": None,
                        "id": "/subscriptions/3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75/resourceGroups/rg2-resource-group",
                        "master_private_ip": "",
                        "master_public_ip": "",
                        "name": "rg2",
                        "status": None,
                        "updated": None,
                    },
                ]
            },
        )

    async def test_list_images(self):
        headers = {
            "Accept": "application/json",
            "subscriptionid": "test",
            "tenantid": "test",
            "appid": "test",
            "extra": "location=test;publisher=test;offer=test;skus=test",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                url=f"http://{self._hostname}:{self._port}/azure/images",
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "images": [
                    {
                        "id": (
                            "/Subscriptions/foo/Providers/Microsoft.Compute/Locations/test"
                            "/Publishers/test/ArtifactTypes/VMImage/Offers/test/Skus/test/Versions/1.2"
                        ),
                        "name": "image1",
                        "extra": {"location": "test", "tags": None},
                    },
                    {
                        "id": (
                            "/Subscriptions/foo/Providers/Microsoft.Compute/Locations/test"
                            "/Publishers/test/ArtifactTypes/VMImage/Offers/test/Skus/test/Versions/1.3"
                        ),
                        "name": "cirros",
                        "extra": {"location": "test", "tags": None},
                    },
                ]
            },
        )

    async def test_get_partition_existed(self):
        async with aiohttp.ClientSession(headers=self._default_headers) as session:
            async with session.get(
                url=(
                    f"http://{self._hostname}:{self._port}/azure/partitions//subscriptions/foo"
                    "/resourceGroups/rg1-resource-group"
                ),
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "compute_instances_ips": [],
                "created": None,
                "description": None,
                "id": "/subscriptions/3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75/resourceGroups/rg1-resource-group",
                "master_private_ip": "",
                "master_public_ip": "",
                "name": "rg1",
                "status": None,
                "updated": None,
            },
        )

    async def test_get_partition_absent(self):
        async with aiohttp.ClientSession(headers=self._default_headers) as session:
            async with session.get(
                url=(
                    f"http://{self._hostname}:{self._port}/azure/partitions//subscriptions/foo"
                    "/resourceGroups/foo-resource-group"
                ),
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(data, {"detail": "Partition not found"})

    async def test_get_image_existed(self):
        img_id = (
            "/Subscriptions/foo/Providers/Microsoft.Compute/"
            "Locations/test/Publishers/test/ArtifactTypes/VMImage/"
            "Offers/test/Skus/test/Versions/1.2"
        )
        headers = {
            "Accept": "application/json",
            "tenantid": "test",
            "appid": "test",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(
                url=f"http://{self._hostname}:{self._port}/azure/images/{img_id}",
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "id": (
                    "/Subscriptions/foo/Providers/Microsoft.Compute/Locations"
                    "/test/Publishers/test/ArtifactTypes/VMImage/Offers/test/Skus/test/Versions/1.2"
                ),
                "name": "image1",
                "extra": {"location": "test", "tags": None},
            },
        )

    async def test_get_image_absent(self):
        img_id = (
            "/Subscriptions/foo/Providers/Microsoft.Compute/"
            "Locations/test/Publishers/test/ArtifactTypes/VMImage/"
            "Offers/test/Skus/test/Versions/2.4"
        )
        async with aiohttp.ClientSession(headers=self._default_headers) as session:
            async with session.get(
                url=f"http://{self._hostname}:{self._port}/azure/images/{img_id}",
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(data, {"detail": "Image not found"})

    async def test_delete_partition_existed(self):
        async with aiohttp.ClientSession(headers=self._default_headers) as session:
            async with session.delete(
                url=f"http://{self._hostname}:{self._port}/azure/partitions//subscriptions/foo/resourceGroups/rg1",
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(data, {"result": "Deletion started"})

    async def test_delete_partition_absent(self):
        async with aiohttp.ClientSession(headers=self._default_headers) as session:
            async with session.delete(
                url=f"http://{self._hostname}:{self._port}/azure/partitions//subscriptions/foo/resourceGroups/bar",
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(data, {"detail": "Cannot delete partition"})

    async def test_create_partition(self):
        headers = {
            "Accept": "application/json",
            "subscriptionid": "test",
            "tenantid": "test",
            "appid": "test",
            "containerregistryuser": "user",
            "containerregistrypass": "pass",
            "osversion": "ubuntu-22.04",
            "containerimage": "swmregistry.azurecr.io/jupyter/datascience-notebook:hub-3.1.1",
            "flavorname": "Standard_B2s",
            "username": "user",
            "count": "1",
            "jobid": "3579a076-9924-11ee-ba53-a3132f7ae2fb",
            "partname": "part1",
            "runtime": "swm_source=ssh, ssh_pub_key=ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEA7GA",
            "location": "eastus",
            "ports": "10001,10022",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                url=f"http://{self._hostname}:{self._port}/azure/partitions",
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(list(data.keys()), ["partition"])
        self.assertTrue(isinstance(data["partition"]["id"], str))

    async def test_create_partition_invalid_count(self):
        headers = {
            "Accept": "application/json",
            "subscriptionid": "test",
            "tenantid": "test",
            "appid": "test",
            "containerregistryuser": "user",
            "containerregistrypass": "pass",
            "osversion": "ubuntu-22.04",
            "containerimage": "swmregistry.azurecr.io/jupyter/datascience-notebook:hub-3.1.1",
            "flavorname": "Standard_B2s",
            "username": "user",
            "count": "0",
            "jobid": "3579a076-9924-11ee-ba53-a3132f7ae2fb",
            "partname": "part-invalid",
            "runtime": "swm_source=ssh, ssh_pub_key=ssh-rsa AAAAB3NzaC1yc2EAAAABIwAAAQEA7GA",
            "location": "eastus",
            "ports": "10001,10022",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(
                url=f"http://{self._hostname}:{self._port}/azure/partitions",
                json={"pem_data": "test"},
            ) as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertIn("detail", data)


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
            storage_key="storagekey",
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

        network_interfaces = [r for r in template["resources"] if r["type"] == "Microsoft.Network/networkInterfaces"]
        virtual_machines = [r for r in template["resources"] if r["type"] == "Microsoft.Compute/virtualMachines"]
        extensions = [r for r in template["resources"] if r["type"] == "Microsoft.Compute/virtualMachines/extensions"]

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

    def test_compute_vm_dependencies_preserve_original_and_use_compute_nic(self):
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
        self.assertNotIn(
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
            "[resourceId('Microsoft.Network/virtualNetworks/subnets', parameters('virtualNetworkName'), parameters('subnetName'))]",
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

        self.assertIn('if [[ "$HOST_NAME" == *-main ]]; then', cloud_init_script)
        self.assertIn(
            "MAIN_INSTANCE_HOSTNAME=$(echo \"$HOST_NAME\" | sed -E 's/-compute[0-9]+$/-main/')",
            cloud_init_script,
        )

    def test_cloud_init_script_configures_nfs_for_shared_home_mount(self):
        cloud_init_script = self._render_cloud_init_script()

        self.assertIn("exportfs -ra", cloud_init_script)
        self.assertIn("systemctl enable nfs-kernel-server", cloud_init_script)
        self.assertIn('echo "$MAIN_INSTANCE_PRIVATE_IP:/home /home nfs', cloud_init_script)
        self.assertIn('resolved_ip=$(getent hosts "$MAIN_INSTANCE_HOSTNAME"', cloud_init_script)
