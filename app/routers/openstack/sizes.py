import typing

from fastapi import APIRouter, Header

from .connector import OpenStackConnector
from .models import ImageInfo, convert_to_flavor

CONNECTOR = OpenStackConnector()
ROUTER = APIRouter()


@ROUTER.get("/openstack/flavors")
async def list_flavors(username: str = Header(None), password: str = Header(None)):
    CONNECTOR.reinitialize(username, password, "compute")
    flavor_list: typing.List[ImageInfo] = []
    if sizes := CONNECTOR.list_sizes():
        for item in sizes:
            flavor_list.append(convert_to_flavor(item))
    return {"flavors": flavor_list}
