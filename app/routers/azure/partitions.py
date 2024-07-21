import http
import logging
import traceback
import typing

from fastapi import APIRouter, Body, Header, HTTPException

from ..models import HttpBody, PartInfo
from .connector import AzureConnector
from .converters import convert_to_partition

CONNECTOR = AzureConnector()
EMPTY_HEADER = Header(None)
LOG = logging.getLogger("swm")
ROUTER = APIRouter()
EMPTY_BODY = Body(None)


@ROUTER.post("/azure/partitions")
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
    ports: str = EMPTY_HEADER,
):
    CONNECTOR.reinitialize(username, password, "orchestration")
    result = CONNECTOR.create_deployment(
        tenantname,
        partname,
        imagename,
        flavorname,
        keyname,
        count,
        jobid,
        runtime,
        ports,
    )
    LOG.info(f"Create Azure partition {partname} for tenant {tenantname}, job id: {jobid}")
    LOG.debug(f"Partition {partname} creation options:")
    LOG.debug(f" * username: {username}")
    LOG.debug(f" * image: {imagename}")
    LOG.debug(f" * flavor: {flavorname}")
    LOG.debug(f" * keyname: {keyname}")
    LOG.debug(f" * extra nodes: {count}")
    LOG.debug(f" * runtime: {runtime}")
    LOG.debug(f" * ports: {ports}")
    return {"partition": result}


@ROUTER.get("/azure/partitions")
async def list_partitions(
    subscriptionid: str = EMPTY_HEADER,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
):
    CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
    try:
        partitions: typing.List[PartInfo] = []
        for resource_group_info in CONNECTOR.list_resource_groups():
            partitions.append(convert_to_partition(resource_group_info))
        return {"partitions": partitions}
    except Exception as e:
        return {"error": traceback.format_exception(e)}


@ROUTER.get("/azure/partitions/{id}")
async def get_partition_info(id: str, username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    try:
        CONNECTOR.reinitialize(username, password, "orchestration")
        stack = CONNECTOR.get_stack(id)
        if not stack:
            raise HTTPException(
                status_code=http.client.NOT_FOUND,
                detail="Partition not found",
            )
        return convert_to_partition(stack)
    except Exception as e:
        return {"error": traceback.format_exception(e)}


@ROUTER.delete("/azure/partitions//subscriptions/{subscriptionid}/resourceGroups/{partitionname}")
async def delete_partition(
    subscriptionid: str,
    partitionname: str,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
):
    try:
        CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
        result = CONNECTOR.delete_resource_group(partitionname)
        return {"result": result}
    except Exception as e:
        return {"error": traceback.format_exception(e)}
