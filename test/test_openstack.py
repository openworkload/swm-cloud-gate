import os
import socket
import asyncio
from multiprocessing import Process

import aiohttp
import uvicorn
import asynctest


class TestOpenstackGate(asynctest.TestCase):

    _hostname: str = socket.gethostname()
    _port: int = 8445

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
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"http://{self._hostname}:{self._port}/openstack/flavors") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "flavors": [
                    {"cpus": 2, "id": "p1", "mem": 1073741824, "name": "flavor1", "price": 3.0, "storage": 12884901888},
                    {
                        "cpus": 8,
                        "id": "p2",
                        "mem": 2147483648,
                        "name": "flavor2",
                        "price": 8.0,
                        "storage": 154618822656,
                    },
                ]
            },
        )

    async def test_list_partitions(self):
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"http://{self._hostname}:{self._port}/openstack/partitions") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "partitions": [
                    {
                        "compute_instances_ips": ["10.0.0.101"],
                        "created": "2021-01-02T15:18:39",
                        "description": "Test stack 1",
                        "id": "s1",
                        "master_private_ip": "10.0.0.108",
                        "master_public_ip": "172.28.128.153",
                        "name": "stack1",
                        "status": "creating",
                        "updated": "2021-01-02T16:18:39",
                    },
                    {
                        "compute_instances_ips": ["10.0.0.102"],
                        "created": "2020-11-12T10:00:00",
                        "description": "Test stack 2",
                        "id": "s2",
                        "master_private_ip": "10.0.0.101",
                        "master_public_ip": "172.28.128.154",
                        "name": "stack2",
                        "status": "succeeded",
                        "updated": "2021-01-02T11:18:39",
                    },
                ]
            },
        )

    async def test_list_images(self):
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"http://{self._hostname}:{self._port}/openstack/images") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "images": [
                    {"id": "i1", "name": "image1", "extra": {"status": "creating"}},
                    {"id": "i2", "name": "cirros", "extra": {"status": "created"}},
                ]
            },
        )

    async def test_get_partition_existed(self):
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"http://{self._hostname}:{self._port}/openstack/partitions/s1") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "compute_instances_ips": ["10.0.0.101"],
                "created": "2021-01-02T15:18:39",
                "description": "Test stack 1",
                "id": "s1",
                "master_private_ip": "10.0.0.108",
                "master_public_ip": "172.28.128.153",
                "name": "stack1",
                "status": "creating",
                "updated": "2021-01-02T16:18:39",
            },
        )

    async def test_get_partition_absent(self):
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"http://{self._hostname}:{self._port}/openstack/partitions/foo") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(data, {"detail": "Partition not found"})

    async def test_get_image_existed(self):
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"http://{self._hostname}:{self._port}/openstack/images/i1") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(
            data,
            {
                "id": "i1",
                "name": "image1",
                "extra": {"status": "creating"},
            },
        )

    async def test_get_image_absent(self):
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(f"http://{self._hostname}:{self._port}/openstack/images/foo") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(data, {"detail": "Image not found"})

    async def test_delete_partition_existed(self):
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.delete(f"http://{self._hostname}:{self._port}/openstack/partitions/s1") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(data, {"result": "Deletion started"})

    async def test_delete_partition_absent(self):
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.delete(f"http://{self._hostname}:{self._port}/openstack/partitions/foo") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(data, {"result": "Stack with id foo not found"})

    async def test_create_partition(self):
        headers = {
            "Accept": "application/json",
            "username": "demo1",
            "password": "demo1",
            "partname": "part1",
            "tenantname": "demo1",
            "imagename": "cirros",
            "flavorname": "m1.micro",
            "keyname": "demo1",
            "count": "0",
            "jobid": "3579a076-9924-11ee-ba53-a3132f7ae2fb",
            "runtime": "swm_source=http://10.0.2.15/swm-worker.tar.gz",
            "ssh_pub_key": "ssh-rsa ABCDEFGhijklmnop",
            "ports": "10001,10022",
            "containerimage": "docker://host/ubuntu22.04",
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.post(f"http://{self._hostname}:{self._port}/openstack/partitions") as resp:
                try:
                    data = await resp.json()
                except aiohttp.client_exceptions.ContentTypeError:
                    data = await resp.text()
        self.assertEqual(list(data.keys()), ["partition"])
        self.assertTrue(isinstance(data["partition"]["id"], str))
