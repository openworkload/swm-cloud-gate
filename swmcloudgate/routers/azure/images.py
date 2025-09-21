import http
import logging
import traceback

from fastapi import Body, Header, APIRouter, HTTPException

from swmcloudgate import config

from ..models import HttpBody, ImageInfo
from .connector import AzureConnector
from .converters import convert_to_image, extract_parameters

LOG = logging.getLogger("swm")
CONNECTOR = AzureConnector()
EMPTY_HEADER = Header(None)
EMPTY_BODY = Body(None)
ROUTER = APIRouter()


@ROUTER.get(
    "/azure/images//Subscriptions/{subscriptionid}/Providers/Microsoft.Compute"
    "/Locations/{location}/Publishers/{publisher}/ArtifactTypes/VMImage"
    "/Offers/{offer}/Skus/{skus}/Versions/{version}"
)
async def get_image_info(
    subscriptionid: str,
    location: str,
    publisher: str,
    offer: str,
    skus: str,
    version: str,
    body: HttpBody = EMPTY_BODY,
) -> ImageInfo:
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
        if image := CONNECTOR.find_image(location, publisher, offer, skus, version):
            return convert_to_image(image)
    except Exception as e:
        LOG.error(traceback.format_exception(e))
    raise HTTPException(
        status_code=http.client.NOT_FOUND,
        detail="Image not found",
    )


@ROUTER.get("/azure/images")
async def list_images(
    extra: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
) -> dict[str, str | list[ImageInfo]]:
    try:
        extra_map = extract_parameters(extra)
        location = extra_map.get("location")
        if not location:
            msg = "Extra parameter is not specified: location"
            LOG.warning(msg)
            return {"error": msg}

        settings = config.get_settings()

        publisher = settings.providers.azure.vm_image.publisher
        offer = settings.providers.azure.vm_image.offer
        skus = settings.providers.azure.vm_image.skus

        if not publisher:
            msg = "Extra parameter is not specified: publisher"
            LOG.warning(msg)
            return {"error": msg}
        if not offer:
            msg = "Extra parameter is not specified: offer"
            LOG.warning(msg)
            return {"error": msg}

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
        image_list: list[ImageInfo] = []

        for image in CONNECTOR.list_images(location, publisher, offer, skus):
            image_list.append(convert_to_image(image))

    except Exception as e:
        LOG.error(traceback.format_exception(e))
        raise HTTPException(
            status_code=http.client.INTERNAL_SERVER_ERROR,
            detail="Cannot get images",
        )
    return {"images": image_list}
