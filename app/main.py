import logging

from fastapi import FastAPI

from .routers.openstack import images as openstack_images
from .routers.openstack import partitions as openstack_partitions
from .routers.openstack import sizes as openstack_sizes

LOGGER = logging.getLogger("swm")
LOGGER.setLevel(logging.DEBUG)

app = FastAPI(debug=True)
app.include_router(openstack_partitions.ROUTER)
app.include_router(openstack_images.ROUTER)
app.include_router(openstack_sizes.ROUTER)
