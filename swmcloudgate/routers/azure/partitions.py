import http
import typing
import logging
import traceback

from fastapi import Body, Header, APIRouter, HTTPException

from ..models import HttpBody, PartInfo
from .connector import AzureConnector
from .converters import convert_to_partition

LOG = logging.getLogger("swm")
CONNECTOR = AzureConnector()
ROUTER = APIRouter()
EMPTY_HEADER = Header(None)
EMPTY_BODY = Body(None)


@ROUTER.post("/azure/partitions")
async def create_partition(
    subscriptionid: str = EMPTY_HEADER,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    containerregistryuser: str = EMPTY_HEADER,
    containerregistrypass: str = EMPTY_HEADER,
    osversion: str = EMPTY_HEADER,
    containerimage: str = EMPTY_HEADER,
    flavorname: str = EMPTY_HEADER,
    username: str = EMPTY_HEADER,
    count: str = EMPTY_HEADER,
    jobid: str = EMPTY_HEADER,
    partname: str = EMPTY_HEADER,
    runtime: str = EMPTY_HEADER,
    location: str = EMPTY_HEADER,
    ports: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
):
    LOG.info(f"Create Azure partition for job {jobid}")
    LOG.debug("Partition creation options:")
    LOG.debug(f" * subscription: {subscriptionid}")
    LOG.debug(f" * tenant: {tenantid}")
    LOG.debug(f" * app: {appid}")
    LOG.debug(f" * partition: {partname}")
    LOG.debug(f" * osversion: {osversion}")
    LOG.debug(f" * containerimage: {containerimage}")
    LOG.debug(f" * flavor: {flavorname}")
    LOG.debug(f" * username: {username}")
    LOG.debug(f" * extra nodes: {count}")
    LOG.debug(f" * runtime: {runtime}")
    LOG.debug(f" * location: {location}")
    LOG.debug(f" * ports: {ports}")
    CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
    try:
        result, resource_group_name = CONNECTOR.create_deployment(
            jobid,
            partname,
            osversion,
            containerimage,
            containerregistryuser,
            containerregistrypass,
            flavorname,
            username,
            count,
            runtime,
            location,
            ports,
        )
        if result:
            return {"partition": convert_to_partition(result, resource_group_name)}
    except Exception as e:
        LOG.error(traceback.format_exception(e))
        return {"error": traceback.format_exception(e)}
    return {"error": "Cannot create Azure deployment"}


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
            partitions.append(convert_to_partition(resource_group_info, resource_group_info["name"]))
        return {"partitions": partitions}
    except Exception as e:
        LOG.error(traceback.format_exception(e))
        return {"error": traceback.format_exception(e)}


@ROUTER.get("/azure/partitions//subscriptions/{subscriptionid}/resourceGroups/{partitionname}-resource-group")
async def get_partition_by_id(
    subscriptionid: str,
    partitionname: str,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
):
    try:
        CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
        if result := CONNECTOR.get_resource_group(partitionname):
            return convert_to_partition(result, partitionname)
    except Exception as e:
        LOG.error(traceback.format_exception(e))
        return {"error": traceback.format_exception(e)}
    raise HTTPException(
        status_code=http.client.NOT_FOUND,
        detail="Partition not found",
    )


@ROUTER.get("/azure/partitions/{partitionname}")
async def get_partition_by_name(
    partitionname: str,
    subscriptionid: str = EMPTY_HEADER,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
):
    resource_group_name = partitionname + "-resource-group"
    try:
        CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
        if result := CONNECTOR.get_resource_group(resource_group_name):
            return convert_to_partition(result, partitionname)
    except Exception as e:
        LOG.error(traceback.format_exception(e))
    raise HTTPException(
        status_code=http.client.NOT_FOUND,
        detail="Partition not found",
    )


@ROUTER.delete("/azure/partitions//subscriptions/{subscriptionid}/resourceGroups/{resourcegroup}")
async def delete_partition(
    subscriptionid: str,
    resourcegroup: str,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
):
    try:
        CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
        if result := CONNECTOR.delete_resource_group(resourcegroup):
            return {"result": result}
    except Exception as e:
        LOG.error(traceback.format_exception(e))
    raise HTTPException(
        status_code=http.client.INTERNAL_SERVER_ERROR,
        detail="Cannot delete partition",
    )
