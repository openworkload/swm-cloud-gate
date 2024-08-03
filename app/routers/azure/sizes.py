import logging
import traceback

from fastapi import APIRouter, Body, Header

from app import cache

from ..models import HttpBody, ImageInfo
from .connector import AzureConnector
from .converters import convert_to_flavor

LOG = logging.getLogger("swm")
CONNECTOR = AzureConnector()
ROUTER = APIRouter()
EMPTY_HEADER = Header(None)
EMPTY_BODY = Body(None)


@ROUTER.get("/azure/flavors")
async def list_flavors(
    subscriptionid: str = EMPTY_HEADER,
    tenantid: str = EMPTY_HEADER,
    appid: str = EMPTY_HEADER,
    location: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
) -> dict[str, str | list[ImageInfo]]:
    if data := cache.data_cache("flavors").fetch_and_update([location]):
        LOG.debug(f"Flavors are taken from cache (amount={len(data)})")
        return {"flavors": data}
    LOG.debug("Flavors not found in the cache => retrieve from Azure")
    CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
    flavor_list: list[ImageInfo] = []
    try:
        if sizes := CONNECTOR.list_sizes(location):
            for item in sizes:
                flavor_list.append(convert_to_flavor(item))
    except Exception as e:
        return {"error": traceback.format_exception(e)}

    changed, deleted = cache.data_cache("flavors").update([location], flavor_list)
    if changed or deleted:
        LOG.debug(f"Flavors cache updated (changed={changed}, deleted={deleted})")
    return {"flavors": flavor_list}
