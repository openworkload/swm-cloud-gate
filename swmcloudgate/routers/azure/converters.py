import re
import uuid
import typing
import hashlib
import logging

from azure.mgmt.compute.models import VirtualMachineSize, VirtualMachineImage
from azure.mgmt.resource.resources.models import DeploymentExtended

from ..models import Flavor, PartInfo, ImageInfo

LOG = logging.getLogger("swm")
PART_ID_PATTERN = re.compile(
    r"^(/subscriptions/[^/]+/resourceGroups/[^/]+)(?:/|$)",
    re.IGNORECASE,
)
# Compute NICs are named "{partition}-compute{N}-NetInt"; main is "{partition}-NetInt".
COMPUTE_NIC_NAME_PATTERN = re.compile(r"^.+-compute(\d+)-NetInt$", re.IGNORECASE)


def _resource_attr(resource: typing.Any, name: str) -> typing.Any:
    if isinstance(resource, dict):
        return resource.get(name)
    return getattr(resource, name, None)


def _nic_private_ip(resource: typing.Any) -> str | None:
    properties = _resource_attr(resource, "properties") or {}
    if not hasattr(properties, "get"):
        return None
    ip_configurations = properties.get("ipConfigurations") or []
    if not ip_configurations:
        return None
    first = ip_configurations[0]
    if not isinstance(first, dict):
        return None
    private_ip = (first.get("properties") or {}).get("privateIPAddress")
    return private_ip or None


def extract_parameters(data: str) -> dict[str, str]:
    if not data:
        return {}
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
        gpus=data.extra.get("gpus", 0),
        mem=data.memory_in_mb,
        storage=data.resource_disk_size_in_mb,
        price=data.extra.get("price", 0.0),
    )


def convert_to_image(data: VirtualMachineImage) -> ImageInfo:
    image = ImageInfo(
        id=data.id,
        name=data.name,
        extra={"tags": getattr(data, "tags", None), "location": getattr(data, "location", None)},
    )
    additional = getattr(data, "additional_properties", None) or {}
    if hasattr(additional, "items"):
        for name, value in additional.items():
            image.extra[name] = value
    offer: str | None = None
    sku: str | None = None
    for name, value in (getattr(data, "extra", None) or {}).items():
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
    compute_ips: list[tuple[int, str]] = []

    for resource in data.get("resources", []):
        properties = _resource_attr(resource, "properties") or {}
        resource_type = _resource_attr(resource, "type")
        if not failed and hasattr(properties, "get"):
            if provisioning_state := properties.get("provisioningState"):
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
        if resource_type == "Microsoft.Network/publicIPAddresses" and hasattr(properties, "get"):
            if public_ip := properties.get("ipAddress"):
                part.master_public_ip = public_ip
        elif resource_type == "Microsoft.Network/networkInterfaces":
            private_ip = _nic_private_ip(resource)
            if not private_ip:
                continue
            nic_name = _resource_attr(resource, "name") or ""
            if match := COMPUTE_NIC_NAME_PATTERN.match(nic_name):
                compute_ips.append((int(match.group(1)), private_ip))
            else:
                part.master_private_ip = private_ip

    compute_ips.sort(key=lambda item: item[0])
    part.compute_instances_ips = [ip for _, ip in compute_ips]

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


def extract_partition_from_deployment_id(resource_id: str, status: str) -> PartInfo | None:
    if isinstance(resource_id, str):
        resource_id = resource_id.strip()
        if m1 := PART_ID_PATTERN.search(resource_id):
            if part_id := m1.group(1):
                if part_name := part_id.split("/")[-1]:
                    return PartInfo(id=part_id, name=part_name, status=status)
    return None
