import http
import logging
import typing

from fastapi import APIRouter, Header, HTTPException

from .connector import OpenStackConnector
from .models import convert_to_image

CONNECTOR = OpenStackConnector()
ROUTER = APIRouter()


@ROUTER.get('/openstack/images/{id}')
async def get_image_info(id: str, username: str = Header(None), password: str = Header(None)):
    CONNECTOR.reinitialize(username, password, 'compute')
    image = CONNECTOR.find_image(id)
    if not image:
        raise HTTPException(
            status_code=http.client.NOT_FOUND,
            detail='Image not found',
        )
    return convert_to_image(image)


@ROUTER.get('/openstack/images')
async def list_images(username: str = Header(None), password: str = Header(None)):
    CONNECTOR.reinitialize(username, password, 'compute')
    images_info: typing.List[ImageInfo] = []
    for image in CONNECTOR.list_images():
        images_info.append(convert_to_image(image))
    return {'images': images_info}
