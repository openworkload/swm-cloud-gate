import logging
import traceback

from fastapi import Body, Header, APIRouter

from ..models import HttpBody, ImageInfo
from .connector import AzureConnector
from .converters import convert_to_flavor, extract_parameters

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
    extra: str = EMPTY_HEADER,
    body: HttpBody = EMPTY_BODY,
) -> dict[str, str | list[ImageInfo]]:

    extra_map = extract_parameters(extra)
    location = extra_map.get("location")
    if not location:
        msg = "Extra parameter is not specified: location"
        LOG.warning(msg)
        return {"error": msg}

    LOG.debug("Flavors not found in the cache => retrieve from Azure")
    CONNECTOR.reinitialize(subscriptionid, tenantid, appid, body.pem_data)
    flavor_list: list[ImageInfo] = []
    try:
        if sizes := CONNECTOR.list_sizes(location):
            for item in sizes:
                flavor_list.append(convert_to_flavor(item))
    except Exception as e:
        LOG.error(traceback.format_exception(e))
        return {"error": traceback.format_exception(e)}

    return {"flavors": flavor_list}
