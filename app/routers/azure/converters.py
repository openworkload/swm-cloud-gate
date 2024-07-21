import hashlib
import typing
import uuid

from azure.mgmt.compute.models import VirtualMachineImage, VirtualMachineSize

from ..models import Flavor, ImageInfo, PartInfo


def convert_to_flavor(data: VirtualMachineSize) -> Flavor:
    hash_object = hashlib.sha256(data.name.encode())
    hash_value = hash_object.hexdigest()
    hash_value = hash_value[:32]
    image_id = uuid.UUID(hash_value, version=4)
    return Flavor(
        id=str(image_id),
        name=data.name,
        cpus=data.number_of_cores,
        mem=data.memory_in_mb,
        storage=data.resource_disk_size_in_mb,
        price=0,
    )


def convert_to_image(data: VirtualMachineImage) -> ImageInfo:
    image = ImageInfo(
        id=data.id,
        name=data.name,
        extra={"tags": data.tags, "location": data.location},
    )
    for name, value in data.additional_properties.items():
        image.extra[name] = value
    for name, value in data.extra.items():
        image.extra[name] = value
    return image


def convert_to_partition(data: dict[str, typing.Any]) -> PartInfo:
    part = PartInfo(id=data["id"], name=data["name"])
    for resource in data.get("resources", []):
        if resource.type == "Microsoft.Network/publicIPAddresses":
            part.master_public_ip = resource.properties.get("ipAddress")
        if resource.type == "Microsoft.Network/networkInterfaces":
            if ip_conf := resource.properties.get("ipConfigurations"):
                part.master_private_ip = ip_conf[0].get("properties", {}).get("privateIPAddress")
    return part
