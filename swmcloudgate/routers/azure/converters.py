import uuid
import typing
import hashlib
import logging

from azure.mgmt.compute.models import VirtualMachineSize, VirtualMachineImage
from azure.mgmt.resource.resources.models import DeploymentExtended

from ..models import Flavor, PartInfo, ImageInfo

LOG = logging.getLogger("swm")


def extract_parameters(data: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for pair in data.split(";"):
        words = pair.split("=")
        if len(words) != 2:
            LOG.warning(f"Cannot parse extra parameter: {pair}")
            continue
        result[words[0]] = words[1]
    return result


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
        price=data.extra.get("price", 0.0),
    )


def convert_to_image(data: VirtualMachineImage) -> ImageInfo:
    image = ImageInfo(
        id=data.id,
        name=data.name,
        extra={"tags": data.tags, "location": data.location},
    )
    for name, value in data.additional_properties.items():
        image.extra[name] = value
    offer: str | None = None
    sku: str | None = None
    for name, value in data.extra.items():
        image.extra[name] = value
        if name == "offer":
            offer = value
        elif name == "sku":
            sku = value
    if offer and sku:
        image.name = f"{offer}/{sku}"
    return image


def convert_to_partition(data: dict[str, typing.Any], resource_group_name: str) -> PartInfo:
    if isinstance(data, DeploymentExtended):
        data = data.as_dict()
    resource_group_id = data["id"].split("/providers")[0]
    part = PartInfo(id=resource_group_id, name=resource_group_name)
    failed = False
    succeeded = False
    updating = False
    deleting = False
    creating = False

    for resource in data.get("resources", []):
        if not failed and resource.properties:
            if provisioning_state := resource.properties.get("provisioningState"):
                provisioning_state = provisioning_state.lower()
                if provisioning_state == "failed":
                    failed = True
                elif provisioning_state == "succeeded":
                    succeeded = True
                elif provisioning_state == "creating":
                    creating = True
                elif provisioning_state == "updating":
                    updating = True
                elif provisioning_state == "deleting":
                    deleting = True
        if resource.type == "Microsoft.Network/publicIPAddresses":
            part.master_public_ip = resource.properties.get("ipAddress")
        if resource.type == "Microsoft.Network/networkInterfaces":
            if ip_conf := resource.properties.get("ipConfigurations"):
                part.master_private_ip = ip_conf[0].get("properties", {}).get("privateIPAddress")

    if failed:
        part.status = "failed"
    elif deleting:
        part.status = "deleting"
    elif updating:
        part.status = "updating"
    elif creating:
        part.status = "creating"
    elif succeeded:
        part.status = "succeeded"

    return part
