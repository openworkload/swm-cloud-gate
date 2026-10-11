import http
import typing
import logging
import traceback
from typing import Optional, Annotated

from fastapi import Header, APIRouter, HTTPException

from .auth import OpenStackAuthError, resolve_openstack_credentials
from ..models import ImageInfo
from .connector import OpenStackConnector
from .converters import convert_to_image

LOG = logging.getLogger("swm")
ROUTER = APIRouter()


def _connector(username: Optional[str], password: Optional[str], service: str) -> OpenStackConnector:
    user, passwd = resolve_openstack_credentials(username, password)
    return OpenStackConnector(user, passwd, service)


@ROUTER.get("/openstack/images/{id}")
async def get_image_info(
    id: str,
    username: Annotated[Optional[str], Header(convert_underscores=False)] = None,
    password: Annotated[Optional[str], Header(convert_underscores=False)] = None,
):
    try:
        connector = _connector(username, password, "compute")
        if image := connector.find_image(id):
            return convert_to_image(image)
    except OpenStackAuthError as e:
        raise HTTPException(status_code=http.client.UNAUTHORIZED, detail=str(e)) from e
    except Exception as e:
        LOG.error(traceback.format_exception(e))
    raise HTTPException(
        status_code=http.client.NOT_FOUND,
        detail="Image not found",
    )


@ROUTER.get("/openstack/images")
async def list_images(
    username: Annotated[Optional[str], Header(convert_underscores=False)] = None,
    password: Annotated[Optional[str], Header(convert_underscores=False)] = None,
):
    image_list: typing.List[ImageInfo] = []
    try:
        connector = _connector(username, password, "compute")
        for image in connector.list_images():
            image_list.append(convert_to_image(image))
    except OpenStackAuthError as e:
        raise HTTPException(status_code=http.client.UNAUTHORIZED, detail=str(e)) from e
    except Exception as e:
        LOG.error(traceback.format_exception(e))
        raise HTTPException(
            status_code=http.client.INTERNAL_SERVER_ERROR,
            detail="Cannot get images",
        )
    return {"images": image_list}
