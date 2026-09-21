import unittest
from types import SimpleNamespace

from swmcloudgate.routers.azure.converters import convert_to_partition


def _nic(name: str, private_ip: str, provisioning_state: str = "Succeeded"):
    return SimpleNamespace(
        type="Microsoft.Network/networkInterfaces",
        name=name,
        properties={
            "provisioningState": provisioning_state,
            "ipConfigurations": [{"properties": {"privateIPAddress": private_ip}}],
        },
    )


def _public_ip(address: str):
    return SimpleNamespace(
        type="Microsoft.Network/publicIPAddresses",
        name="part-PublicIP",
        properties={"ipAddress": address, "provisioningState": "Succeeded"},
    )


class TestAzureConvertToPartition(unittest.TestCase):
    def test_splits_main_and_compute_nic_private_ips(self):
        data = {
            "id": "/subscriptions/sub/resourceGroups/part-resource-group",
            "resources": [
                _public_ip("20.1.2.3"),
                _nic("part-compute2-NetInt", "10.0.0.8"),
                _nic("part-NetInt", "10.0.0.4"),
                _nic("part-compute1-NetInt", "10.0.0.7"),
            ],
        }

        part = convert_to_partition(data, "part")

        self.assertEqual(part.master_public_ip, "20.1.2.3")
        self.assertEqual(part.master_private_ip, "10.0.0.4")
        self.assertEqual(part.compute_instances_ips, ["10.0.0.7", "10.0.0.8"])
        self.assertEqual(part.status, "succeeded")

    def test_dict_resources_are_supported(self):
        data = {
            "id": "/subscriptions/sub/resourceGroups/part-resource-group",
            "resources": [
                {
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "part-NetInt",
                    "properties": {
                        "provisioningState": "Succeeded",
                        "ipConfigurations": [{"properties": {"privateIPAddress": "10.0.0.4"}}],
                    },
                },
                {
                    "type": "Microsoft.Network/networkInterfaces",
                    "name": "part-compute1-NetInt",
                    "properties": {
                        "provisioningState": "Succeeded",
                        "ipConfigurations": [{"properties": {"privateIPAddress": "10.0.0.7"}}],
                    },
                },
            ],
        }

        part = convert_to_partition(data, "part")

        self.assertEqual(part.master_private_ip, "10.0.0.4")
        self.assertEqual(part.compute_instances_ips, ["10.0.0.7"])

    def test_skips_nics_without_private_ip(self):
        data = {
            "id": "/subscriptions/sub/resourceGroups/part-resource-group",
            "resources": [
                SimpleNamespace(
                    type="Microsoft.Network/networkInterfaces",
                    name="part-NetInt",
                    properties={
                        "provisioningState": "Succeeded",
                        "ipConfigurations": [{"properties": {}}],
                    },
                ),
                _nic("part-compute1-NetInt", "10.0.0.7"),
            ],
        }

        part = convert_to_partition(data, "part")

        self.assertEqual(part.master_private_ip, "")
        self.assertEqual(part.compute_instances_ips, ["10.0.0.7"])
