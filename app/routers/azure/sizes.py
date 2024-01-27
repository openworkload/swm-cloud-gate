import typing

from fastapi import APIRouter, Header

from ..models import ImageInfo, convert_to_flavor
from .connector import AzureConnector

CONNECTOR = AzureConnector()
EMPTY_HEADER = Header(None)
ROUTER = APIRouter()


@ROUTER.get("/azure/flavors")
async def list_flavors(username: str = EMPTY_HEADER, password: str = EMPTY_HEADER):
    CONNECTOR.reinitialize(username, password, "compute")
    flavor_list: typing.List[ImageInfo] = []
    if sizes := CONNECTOR.list_sizes():
        for item in sizes:
            flavor_list.append(convert_to_flavor(item))
    return {"flavors": flavor_list}
