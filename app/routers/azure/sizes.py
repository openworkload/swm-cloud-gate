import typing

from fastapi import APIRouter, Body, Header
from pydantic import BaseModel

from ..models import ImageInfo
from .connector import AzureConnector
from .converters import convert_to_flavor

CONNECTOR = AzureConnector()
ROUTER = APIRouter()
EMPTY_HEADER = Header(None)
EMPTY_BODY = Body(None)


class Body(BaseModel):
    pem_data: bytes


@ROUTER.get("/azure/flavors")
async def list_flavors(
    subscriptionid: str = EMPTY_HEADER,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    location: str = EMPTY_HEADER,
    body: Body = EMPTY_BODY,
):
    CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
    flavor_list: typing.List[ImageInfo] = []
    try:
        if sizes := CONNECTOR.list_sizes(location):
            for item in sizes:
                flavor_list.append(convert_to_flavor(item))
    except Exception as e:
        return {"error": str(e)}

    return {"flavors": flavor_list}
