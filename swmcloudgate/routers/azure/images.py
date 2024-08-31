import http
import logging
import traceback

from fastapi import Body, Header, APIRouter, HTTPException

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
    "/Offers/{offer}/Skus/{sku}/Versions/{version}"
)
async def get_image_info(
    subscriptionid: str,
    location: str,
    publisher: str,
    offer: str,
    sku: str,
    version: str,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
) -> ImageInfo:
    try:
        CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
        if image := CONNECTOR.find_image(location, publisher, offer, sku, version):
            return convert_to_image(image)
    except Exception as e:
        LOG.error(traceback.format_exception(e))
    raise HTTPException(
        status_code=http.client.NOT_FOUND,
        detail="Image not found",
    )


@ROUTER.get("/azure/images")
async def list_images(
    subscriptionid: str = EMPTY_HEADER,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    extra: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
) -> dict[str, str | list[ImageInfo]]:

    extra_map = extract_parameters(extra)
    location = extra_map.get("location")
    publisher = extra_map.get("publisher")
    offer = extra_map.get("offer")
    skus = extra_map.get("skus", "")

    if not location:
        msg = "Extra parameter is not specified: location"
        LOG.warning(msg)
        return {"error": msg}
    if not publisher:
        msg = "Extra parameter is not specified: publisher"
        LOG.warning(msg)
        return {"error": msg}
    if not offer:
        msg = "Extra parameter is not specified: offer"
        LOG.warning(msg)
        return {"error": msg}

    CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
    image_list: list[ImageInfo] = []
    try:
        for image in CONNECTOR.list_images(location, publisher, offer, skus):
            image_list.append(convert_to_image(image))
    except Exception as e:
        LOG.error(traceback.format_exception(e))
        raise HTTPException(
            status_code=http.client.INTERNAL_SERVER_ERROR,
            detail="Cannot get images",
        )
    return {"images": image_list}
