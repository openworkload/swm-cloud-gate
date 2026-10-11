import http
import typing
from typing import Optional, Annotated

from fastapi import Header, APIRouter, HTTPException

from .auth import OpenStackAuthError, resolve_openstack_credentials
from ..models import ImageInfo
from .connector import OpenStackConnector
from .converters import convert_to_flavor

ROUTER = APIRouter()


def _connector(username: Optional[str], password: Optional[str], service: str) -> OpenStackConnector:
    user, passwd = resolve_openstack_credentials(username, password)
    return OpenStackConnector(user, passwd, service)


@ROUTER.get("/openstack/flavors")
async def list_flavors(
    username: Annotated[Optional[str], Header(convert_underscores=False)] = None,
    password: Annotated[Optional[str], Header(convert_underscores=False)] = None,
):
    try:
        connector = _connector(username, password, "compute")
    except OpenStackAuthError as e:
        raise HTTPException(status_code=http.client.UNAUTHORIZED, detail=str(e)) from e
    flavor_list: typing.List[ImageInfo] = []
    if sizes := connector.list_sizes():
        for item in sizes:
            flavor_list.append(convert_to_flavor(item))
    return {"flavors": flavor_list}
