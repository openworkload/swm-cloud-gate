import http
import typing

from fastapi import APIRouter, Header, HTTPException

from ..models import ImageInfo
from .connector import OpenStackConnector
from .converters import convert_to_image

CONNECTOR = OpenStackConnector()
EMPTY_HEADER = Header(None)
ROUTER = APIRouter()


@ROUTER.get("/openstack/images/{id}")
async def get_image_info(id: str, username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    CONNECTOR.reinitialize(username, password, "compute")
    image = CONNECTOR.find_image(id)
    if not image:
        raise HTTPException(
            status_code=http.client.NOT_FOUND,
            detail="Image not found",
        )
    return convert_to_image(image)


@ROUTER.get("/openstack/images")
async def list_images(username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    CONNECTOR.reinitialize(username, password, "compute")
    images_info: typing.List[ImageInfo] = []
    for image in CONNECTOR.list_images():
        images_info.append(convert_to_image(image))
    return {"images": images_info}
