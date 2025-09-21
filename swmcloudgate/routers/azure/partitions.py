import http
import json
import typing
import logging
import traceback

from fastapi import Body, Header, APIRouter, HTTPException
from azure.core.exceptions import HttpResponseError

from swmcloudgate import config

from ..models import HttpBody, PartInfo
from .connector import AzureConnector
from .converters import convert_to_partition, extract_partition_from_deployment_id

LOG = logging.getLogger("swm")
CONNECTOR = AzureConnector()
ROUTER = APIRouter()
EMPTY_HEADER = Header(None)
EMPTY_BODY = Body(None)


@ROUTER.post("/azure/partitions")
async def create_partition(
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
    try:
        LOG.info(f"Create Azure partition for job {jobid}")
        LOG.debug("Partition creation options:")
        LOG.debug(f" * partition: {partname}")
        LOG.debug(f" * osversion: {osversion}")
        LOG.debug(f" * containerimage: {containerimage}")
        LOG.debug(f" * flavor: {flavorname}")
        LOG.debug(f" * username: {username}")
        LOG.debug(f" * extra nodes: {count}")
        LOG.debug(f" * runtime: {runtime}")
        LOG.debug(f" * location: {location}")
        LOG.debug(f" * ports: {ports}")

        settings = config.get_settings()

        subscription_id = settings.providers.azure.api_credentials.subscription_id
        tenant_id = settings.providers.azure.api_credentials.tenant_id
        app_id = settings.providers.azure.api_credentials.app_id

        if not subscription_id:
            msg = "No subscription ID"
            LOG.warning(msg)
            return {"error": msg}
        if not tenant_id:
            msg = "No tenant ID"
            LOG.warning(msg)
            return {"error": msg}
        if not app_id:
            msg = "No app ID"
            LOG.warning(msg)
            return {"error": msg}

        container_registry_user = settings.providers.azure.container_registry.user
        container_registry_password = settings.providers.azure.container_registry.password
        storage_account = settings.providers.azure.storage.account
        storage_key = settings.providers.azure.storage.key
        storage_container = settings.providers.azure.storage.container
        user_ssh_cert = settings.providers.azure.user_ssh_cert

        CONNECTOR.reinitialize(subscription_id, tenant_id, app_id, body.pem_data)

        result, resource_group_name = CONNECTOR.create_deployment(
            jobid,
            partname,
            osversion,
            containerimage,
            container_registry_user,
            container_registry_password,
            storage_account,
            storage_key,
            storage_container,
            flavorname,
            username,
            count,
            runtime,
            location,
            ports,
            user_ssh_cert,
        )
        if result:
            return {"partition": convert_to_partition(result, resource_group_name)}

    except HttpResponseError as e:
        if resp := getattr(e, "response", None):
            data = None
            try:
                data = resp.text()
            except Exception:
                pass
            try:
                data_json = json.loads(data)
            except Exception:
                pass
            error_messages: list[str] = []
            partition = None
            if isinstance(data_json, dict):
                if status := data_json.get("status"):
                    error_messages.append(str(status))
                if error := data_json.get("error"):
                    if isinstance(error, dict):
                        if target := error.get("target"):
                            partition = extract_partition_from_deployment_id(target, status="failed")
                        for detail in error.get("details", []):
                            if message := detail.get("message"):
                                error_messages.append(str(message))

            LOG.error(f"From Azure:\n{json.dumps(data_json, indent=2)}")
            LOG.debug(f"Partition: {partition}")

            return {"error": f"Error from Azure: {'; '.join(error_messages)}", "partition": partition}

    except Exception as e:
        LOG.error(traceback.format_exception(e))
        return {"error": traceback.format_exception(e)}

    return {"error": "Cannot create Azure deployment"}


@ROUTER.get("/azure/partitions")
async def list_partitions(
    body: HttpBody = EMPTY_BODY,
):
    try:
        settings = config.get_settings()

        subscription_id = settings.providers.azure.api_credentials.subscription_id
        tenant_id = settings.providers.azure.api_credentials.tenant_id
        app_id = settings.providers.azure.api_credentials.app_id

        if not subscription_id:
            msg = "No subscription ID"
            LOG.warning(msg)
            return {"error": msg}
        if not tenant_id:
            msg = "No tenant ID"
            LOG.warning(msg)
            return {"error": msg}
        if not app_id:
            msg = "No app ID"
            LOG.warning(msg)
            return {"error": msg}

        CONNECTOR.reinitialize(subscription_id, tenant_id, app_id, body.pem_data)

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
    body: HttpBody = EMPTY_BODY,
):
    try:
        settings = config.get_settings()

        tenant_id = settings.providers.azure.api_credentials.tenant_id
        app_id = settings.providers.azure.api_credentials.app_id

        if not tenant_id:
            msg = "No tenant ID"
            LOG.warning(msg)
            return {"error": msg}
        if not app_id:
            msg = "No app ID"
            LOG.warning(msg)
            return {"error": msg}

        CONNECTOR.reinitialize(subscriptionid, tenant_id, app_id, body.pem_data)
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
    body: HttpBody = EMPTY_BODY,
):
    try:
        settings = config.get_settings()

        subscription_id = settings.providers.azure.api_credentials.subscription_id
        tenant_id = settings.providers.azure.api_credentials.tenant_id
        app_id = settings.providers.azure.api_credentials.app_id

        if not subscription_id:
            msg = "No subscription ID"
            LOG.warning(msg)
            return {"error": msg}
        if not tenant_id:
            msg = "No tenant ID"
            LOG.warning(msg)
            return {"error": msg}
        if not app_id:
            msg = "No app ID"
            LOG.warning(msg)
            return {"error": msg}

        CONNECTOR.reinitialize(subscription_id, tenant_id, app_id, body.pem_data)

        resource_group_name = partitionname + "-resource-group"
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
    body: HttpBody = EMPTY_BODY,
):
    try:
        settings = config.get_settings()

        tenant_id = settings.providers.azure.api_credentials.tenant_id
        app_id = settings.providers.azure.api_credentials.app_id

        if not tenant_id:
            msg = "No tenant ID"
            LOG.warning(msg)
            return {"error": msg}
        if not app_id:
            msg = "No app ID"
            LOG.warning(msg)
            return {"error": msg}

        CONNECTOR.reinitialize(subscriptionid, tenant_id, app_id, body.pem_data)
        if result := CONNECTOR.delete_resource_group(resourcegroup):
            return {"result": result}

    except Exception as e:
        LOG.error(traceback.format_exception(e))

    raise HTTPException(
        status_code=http.client.INTERNAL_SERVER_ERROR,
        detail="Cannot delete partition",
    )
