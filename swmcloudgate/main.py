import logging
import os

from fastapi import FastAPI

from . import uvicorn_peercert
from .mtls_middleware import ClientCertPinMiddleware
from .routers.azure import sizes as azure_sizes
from .routers.azure import images as azure_images
from .routers.azure import partitions as azure_partitions
from .routers.openstack import sizes as openstack_sizes
from .routers.openstack import images as openstack_images
from .routers.openstack import partitions as openstack_partitions

LOGGER = logging.getLogger("swm")
LOGGER.setLevel(logging.DEBUG)

# Workers import this module; patch uvicorn before any request is handled.
# Mocked CT sets SWM_GATE_DISABLE_PEER_CERT_PATCH=1 (handshake CERT_REQUIRED remains).
if os.environ.get("SWM_GATE_DISABLE_PEER_CERT_PATCH", "").strip() not in ("1", "true", "yes"):
    uvicorn_peercert.install()

app = FastAPI(debug=True)
app.add_middleware(ClientCertPinMiddleware)

app.include_router(openstack_partitions.ROUTER)
app.include_router(openstack_images.ROUTER)
app.include_router(openstack_sizes.ROUTER)

app.include_router(azure_partitions.ROUTER)
app.include_router(azure_images.ROUTER)
app.include_router(azure_sizes.ROUTER)
