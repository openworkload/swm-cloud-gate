import logging

from fastapi import FastAPI

from .routers.azure import sizes as azure_sizes
from .routers.azure import images as azure_images
from .routers.azure import partitions as azure_partitions
from .routers.openstack import sizes as openstack_sizes
from .routers.openstack import images as openstack_images
from .routers.openstack import partitions as openstack_partitions

LOGGER = logging.getLogger("swm")
LOGGER.setLevel(logging.DEBUG)

app = FastAPI(debug=True)

app.include_router(openstack_partitions.ROUTER)
app.include_router(openstack_images.ROUTER)
app.include_router(openstack_sizes.ROUTER)

app.include_router(azure_partitions.ROUTER)
app.include_router(azure_images.ROUTER)
app.include_router(azure_sizes.ROUTER)
