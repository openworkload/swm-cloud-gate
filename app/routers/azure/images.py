import http
import typing

from fastapi import APIRouter, Header, HTTPException

from ..models import ImageInfo
from .connector import AzureConnector
from .converters import convert_to_image

CONNECTOR = AzureConnector()
EMPTY_HEADER = Header(None)
ROUTER = APIRouter()


@ROUTER.get("/azure/images/{id}")
async def get_image_info(id: str, subscription_id: str, app_id: str, tenant_id: str, password: str):
    CONNECTOR.reinitialize(subscription_id, app_id, tenant_id, password)
    image = CONNECTOR.find_image(id)
    if not image:
        raise HTTPException(
            status_code=http.client.NOT_FOUND,
            detail="Image not found",
        )
    return convert_to_image(image)


@ROUTER.get("/azure/images")
async def list_images(subscription_id: str, app_id: str, tenant_id: str, password: str):
    CONNECTOR.reinitialize(subscription_id, app_id, tenant_id, password)
    images_info: typing.List[ImageInfo] = []
    for image in CONNECTOR.list_images():
        images_info.append(convert_to_image(image))
    return {"images": images_info}
