import http
import typing
import logging

from fastapi import Header, APIRouter, HTTPException

from ..models import PartInfo
from .connector import OpenStackConnector
from .converters import convert_to_partition

CONNECTOR = OpenStackConnector()
EMPTY_HEADER = Header(None)
LOG = logging.getLogger("swm")
ROUTER = APIRouter()


@ROUTER.post("/openstack/partitions")
async def create_partition(
    username: str = EMPTY_HEADER,
    password: str = EMPTY_HEADER,
    tenantname: str = EMPTY_HEADER,
    partname: str = EMPTY_HEADER,
    vmimage: str = EMPTY_HEADER,
    flavorname: str = EMPTY_HEADER,
    keyname: str = EMPTY_HEADER,
    count: str = EMPTY_HEADER,
    jobid: str = EMPTY_HEADER,
    runtime: str = EMPTY_HEADER,
    ports: str = EMPTY_HEADER,
    containerimage: str = EMPTY_HEADER,
):
    CONNECTOR.reinitialize(username, password, "orchestration")
    result = CONNECTOR.create_stack(
        tenantname,
        partname,
        vmimage,
        flavorname,
        keyname,
        count,
        jobid,
        runtime,
        ports,
        containerimage,
    )
    LOG.info(f"Create OpenStack partition {partname} for tenant {tenantname}, job id: {jobid}")
    LOG.debug(f"Partition {partname} creation options:")
    LOG.debug(f" * username: {username}")
    LOG.debug(f" * image: {vmimage}")
    LOG.debug(f" * flavor: {flavorname}")
    LOG.debug(f" * keyname: {keyname}")
    LOG.debug(f" * extra nodes: {count}")
    LOG.debug(f" * runtime: {runtime}")
    LOG.debug(f" * ports: {ports}")
    LOG.debug(f" * container image: {containerimage}")
    return {"partition": result}


@ROUTER.get("/openstack/partitions")
async def list_partitions(username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    CONNECTOR.reinitialize(username, password, "orchestration")
    partitions: typing.List[PartInfo] = []
    for stack in CONNECTOR.list_stacks():
        if "id" not in stack or "stack_name" not in stack:
            LOG.warn(f"Returned stack information is incomplete: {stack}")
            continue
        partitions.append(convert_to_partition(stack))
    return {"partitions": partitions}


@ROUTER.get("/openstack/partitions/{id}")
async def get_partition_info(id: str, username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    CONNECTOR.reinitialize(username, password, "orchestration")
    if stack := CONNECTOR.get_stack(id):
        return convert_to_partition(stack)
    raise HTTPException(
        status_code=http.client.NOT_FOUND,
        detail="Partition not found",
    )


@ROUTER.delete("/openstack/partitions/{id}")
async def delete_partition(id: str, username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    CONNECTOR.reinitialize(username, password, "orchestration")
    result = CONNECTOR.delete_stack(id)
    return {"result": result}
