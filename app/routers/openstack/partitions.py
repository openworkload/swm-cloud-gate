import http
import logging
import typing

from fastapi import APIRouter, Header, HTTPException

from .connector import OpenStackConnector
from .models import convert_to_partition

CONNECTOR = OpenStackConnector()
LOG = logging.getLogger("swm")
ROUTER = APIRouter()


@ROUTER.post("/openstack/partitions")
async def create_partition(
    username: str = Header(None),
    password: str = Header(None),
    tenantname: str = Header(None),
    partname: str = Header(None),
    imagename: str = Header(None),
    flavorname: str = Header(None),
    keyname: str = Header(None),
    count: str = Header(None),
):
    CONNECTOR.reinitialize(username, password, "orchestration")
    result = CONNECTOR.create_stack(tenantname, partname, imagename, flavorname, keyname, count)
    LOG.info(f"Create partition {partname} for tenant {tenantname}")
    return {"partition": result}


@ROUTER.get("/openstack/partitions")
async def list_partitions(username: str = Header(None), password: str = Header(None)):
    CONNECTOR.reinitialize(username, password, "orchestration")
    partitions: typing.List[PartInfo] = []
    for stack in CONNECTOR.list_stacks():
        if "id" not in stack or "stack_name" not in stack:
            LOG.warn(f"Returned stack information is incomplete: {stack}")
            continue
        partitions.append(convert_to_partition(stack))
    return {"partitions": partitions}


@ROUTER.get("/openstack/partitions/{id}")
async def get_partition_info(id: str, username: str = Header(None), password: str = Header(None)):
    CONNECTOR.reinitialize(username, password, "orchestration")
    stack = CONNECTOR.get_stack(id)
    if not stack:
        raise HTTPException(
            status_code=http.client.NOT_FOUND,
            detail="Partition not found",
        )
    return convert_to_partition(stack)


@ROUTER.delete("/openstack/partitions/{id}")
async def delete_partition(id: str, username: str = Header(None), password: str = Header(None)):
    CONNECTOR.reinitialize(username, password, "orchestration")
    result = CONNECTOR.delete_stack(id)
    return {"result": result}
