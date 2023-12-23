import http
import logging
import typing

from fastapi import APIRouter, Header, HTTPException

from .connector import OpenStackConnector
from .models import PartInfo, convert_to_partition

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
    imagename: str = EMPTY_HEADER,
    flavorname: str = EMPTY_HEADER,
    keyname: str = EMPTY_HEADER,
    count: str = EMPTY_HEADER,
    jobid: str = EMPTY_HEADER,
    runtime: str = EMPTY_HEADER,
):
    CONNECTOR.reinitialize(username, password, "orchestration")
    result = CONNECTOR.create_stack(tenantname, partname, imagename, flavorname, keyname, count, jobid, runtime)
    LOG.info(f"Create partition {partname} for tenant {tenantname}, job id: {jobid}")
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
    stack = CONNECTOR.get_stack(id)
    if not stack:
        raise HTTPException(
            status_code=http.client.NOT_FOUND,
            detail="Partition not found",
        )
    return convert_to_partition(stack)


@ROUTER.delete("/openstack/partitions/{id}")
async def delete_partition(id: str, username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    CONNECTOR.reinitialize(username, password, "orchestration")
    result = CONNECTOR.delete_stack(id)
    return {"result": result}
