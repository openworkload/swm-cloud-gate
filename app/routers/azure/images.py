import logging
import traceback

from fastapi import APIRouter, Body, Header

from app import cache

from ..models import HttpBody, ImageInfo
from .connector import AzureConnector
from .converters import convert_to_image

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
        return {"error": traceback.format_exception(e)}
    return {"error": "Image not found"}


@ROUTER.get("/azure/images")
async def list_images(
    subscriptionid: str = EMPTY_HEADER,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    location: str = EMPTY_HEADER,
    publisher: str = EMPTY_HEADER,
    offer: str = EMPTY_HEADER,
    skus: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
) -> dict[str, str | list[ImageInfo]]:
    cache_key = [location, publisher, offer, skus] if skus else [location, publisher, offer]
    if data := cache.data_cache("vmimages").fetch_and_update(cache_key):
        LOG.debug(f"VM images are taken from cache (amount={len(data)})")
        return {"images": data}
    CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
    image_list: list[ImageInfo] = []
    try:
        for image in CONNECTOR.list_images(location, publisher, offer, skus):
            image_list.append(convert_to_image(image))
    except Exception as e:
        return {"error": traceback.format_exception(e)}

    changed, deleted = cache.data_cache("vmimages").update(cache_key, image_list)
    if changed or deleted:
        LOG.debug(f"VM image cache updated (changed={changed}, deleted={deleted})")

    return {"images": image_list}
