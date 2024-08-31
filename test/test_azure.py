import os
import socket
import asyncio
from multiprocessing import Process

import aiohttp
import uvicorn
import asynctest


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
        self.proc = Process(
            target=uvicorn.run,
            args=("swmcloudgate.main:app",),
            kwargs={
                "host": self._hostname,
                "port": self._port,
                "log_config": "logging.yaml",
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
                        "id": "9348abe1-2a12-4ba7-9942-920a58fa887f",
                        "mem": 1073,
                        "name": "flavor1",
                        "price": 3.0,
                        "storage": 12884,
                    },
                    {
                        "cpus": 8,
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
            "count": "0",
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
