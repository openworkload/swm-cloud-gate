import os
import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from . import uvicorn_peercert
from .routers.azure import sizes as azure_sizes
from .routers.azure import images as azure_images
from .routers.azure import partitions as azure_partitions
from .mtls_middleware import ClientCertPinMiddleware
from .routers.openstack import sizes as openstack_sizes
from .routers.openstack import images as openstack_images
from .routers.openstack import partitions as openstack_partitions

LOGGER = logging.getLogger("swm")
LOGGER.setLevel(logging.DEBUG)

# Workers import this module; patch uvicorn before any request is handled.
# Mocked CT sets SWM_GATE_DISABLE_PEER_CERT_PATCH=1 (handshake CERT_REQUIRED remains).
if os.environ.get("SWM_GATE_DISABLE_PEER_CERT_PATCH", "").strip() not in ("1", "true", "yes"):
    uvicorn_peercert.install()

app = FastAPI(debug=False)
app.add_middleware(ClientCertPinMiddleware)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return a generic 500; keep stack traces in server logs only."""
    LOGGER.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(openstack_partitions.ROUTER)
app.include_router(openstack_images.ROUTER)
app.include_router(openstack_sizes.ROUTER)

app.include_router(azure_partitions.ROUTER)
app.include_router(azure_images.ROUTER)
app.include_router(azure_sizes.ROUTER)
