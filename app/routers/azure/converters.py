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
    return ImageInfo(id=data.id, name=data.name)


def convert_to_partition(data: typing.Dict[str, typing.Any]) -> PartInfo:
    return PartInfo(id=part["id"], name=data["stack_name"])
