import logging
import typing

from fastapi import FastAPI

from .routers.openstack import images as openstack_images
from .routers.openstack import partitions as openstack_partitions
from .routers.openstack import sizes as openstack_sizes

logger = logging.getLogger("fastapi")
logger.setLevel(logging.DEBUG)

logging.config.fileConfig("app/logging.conf", disable_existing_loggers=False)


app = FastAPI(debug=True)
app.include_router(openstack_partitions.ROUTER)
app.include_router(openstack_images.ROUTER)
app.include_router(openstack_sizes.ROUTER)
