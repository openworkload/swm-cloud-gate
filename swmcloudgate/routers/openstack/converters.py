import typing

from libcloud.compute.base import NodeSize, NodeImage

from ..models import Flavor, PartInfo, ImageInfo


def convert_to_partition(stack: typing.Dict[str, typing.Any]) -> PartInfo:
    part = PartInfo(id=stack["id"], name=stack["stack_name"])
    part.created = stack.get("creation_time")
    part.updated = stack.get("updated_time")
    part.description = stack.get("description")

    for it in stack.get("outputs", []):
        for name, value in it.items():
            if name == "output_key":
                if value == "compute_instances_private_ips":
                    part.compute_instances_ips = it.get("output_value", [])
                elif value == "master_instance_private_ip":
                    part.master_private_ip = it.get("output_value", "")
                elif value == "master_instance_public_ip":
                    part.master_public_ip = it.get("output_value", "")

    if stack_status := stack.get("stack_status"):
        if stack_status == "CREATE_IN_PROGRESS":
            part.status = "creating"
        elif stack_status == "CREATE_COMPLETE":
            part.status = "succeeded"
        elif stack_status == "CREATE_FAILED":
            part.status = "failed"
        elif stack_status == "UPDATE_IN_PROGRESS":
            part.status = "updating"
        elif stack_status == "UPDATE_IN_COMPLETE":
            part.status = "succeeded"
        elif stack_status == "UPDATE_FAILED":
            part.status = "failed"
        elif stack_status == "DELETE_IN_PROGRESS":
            part.status = "deleting"
        elif stack_status == "DELETE_COMPLETE":
            part.status = "deleted"
        elif stack_status == "DELETE_FAILED":
            part.status = "failed"
        else:
            part.status = "unknown"

    return part


def convert_to_flavor(data: NodeSize) -> Flavor:
    return Flavor(id=data.id, name=data.name, cpus=data.vcpus, mem=data.ram, storage=data.disk, price=data.price)


def convert_to_image(image: NodeImage) -> ImageInfo:
    return ImageInfo(id=image.id, name=image.name, extra=image.extra)
