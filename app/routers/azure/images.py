import http

from fastapi import APIRouter, Body, Header, HTTPException

from ..models import HttpBody, ImageInfo
from .connector import AzureConnector
from .converters import convert_to_image

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
    CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
    if image := CONNECTOR.find_image(location, publisher, offer, sku, version):
        return convert_to_image(image)
    raise HTTPException(
        status_code=http.client.NOT_FOUND,
        error=f"Image not found by id: {image_id}",
    )


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
    CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
    images_info: list[ImageInfo] = []
    try:
        for image in CONNECTOR.list_images(location, publisher, offer, skus):
            images_info.append(convert_to_image(image))
    except Exception as e:
        return {"error": str(e)}
    return {"images": images_info}
