import typing

from libcloud.compute.base import NodeImage, NodeSize

from ..models import Flavor, ImageInfo, PartInfo


def convert_to_partition(stack: typing.Dict[str, typing.Any]) -> PartInfo:
    part = PartInfo(id=stack["id"], name=stack["stack_name"])
    part.created = stack.get("creation_time", None)
    part.updated = stack.get("updated_time", None)
    part.status = stack.get("stack_status", None)
    part.description = stack.get("description", None)

    for it in stack.get("outputs", []):
        for name, value in it.items():
            if name == "output_key":
                if value == "compute_instances_private_ips":
                    part.compute_instances_ips = it.get("output_value", [])
                elif value == "master_instance_private_ip":
                    part.master_private_ip = it.get("output_value", "")
                elif value == "master_instance_public_ip":
                    part.master_public_ip = it.get("output_value", "")
    return part


def convert_to_flavor(data: NodeSize) -> Flavor:
    return Flavor(id=data.id, name=data.name, cpus=data.vcpus, mem=data.ram, storage=data.disk, price=data.price)


def convert_to_image(image: NodeImage) -> ImageInfo:
    return ImageInfo(id=image.id, name=image.name, extra=image.extra)
