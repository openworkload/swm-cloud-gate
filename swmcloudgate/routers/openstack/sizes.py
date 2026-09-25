import typing
from typing import Optional, Annotated

from fastapi import Header, APIRouter

from ..models import ImageInfo
from .connector import OpenStackConnector
from .converters import convert_to_flavor

CONNECTOR = OpenStackConnector()
ROUTER = APIRouter()


@ROUTER.get("/openstack/flavors")
async def list_flavors(
    username: Annotated[Optional[str], Header(convert_underscores=False)] = None,
    password: Annotated[Optional[str], Header(convert_underscores=False)] = None,
):
    CONNECTOR.reinitialize(username, password, "compute")
    flavor_list: typing.List[ImageInfo] = []
    if sizes := CONNECTOR.list_sizes():
        for item in sizes:
            flavor_list.append(convert_to_flavor(item))
    return {"flavors": flavor_list}
