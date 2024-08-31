import http
import typing
import logging
import traceback

from fastapi import Header, APIRouter, HTTPException

from ..models import ImageInfo
from .connector import OpenStackConnector
from .converters import convert_to_image

LOG = logging.getLogger("swm")
CONNECTOR = OpenStackConnector()
EMPTY_HEADER = Header(None)
ROUTER = APIRouter()


@ROUTER.get("/openstack/images/{id}")
async def get_image_info(id: str, username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    try:
        CONNECTOR.reinitialize(username, password, "compute")
        if image := CONNECTOR.find_image(id):
            return convert_to_image(image)
    except Exception as e:
        LOG.error(traceback.format_exception(e))
    raise HTTPException(
        status_code=http.client.NOT_FOUND,
        detail="Image not found",
    )


@ROUTER.get("/openstack/images")
async def list_images(username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    image_list: typing.List[ImageInfo] = []
    try:
        CONNECTOR.reinitialize(username, password, "compute")
        for image in CONNECTOR.list_images():
            image_list.append(convert_to_image(image))
    except Exception as e:
        LOG.error(traceback.format_exception(e))
        raise HTTPException(
            status_code=http.client.INTERNAL_SERVER_ERROR,
            detail="Cannot get images",
        )
    return {"images": image_list}
