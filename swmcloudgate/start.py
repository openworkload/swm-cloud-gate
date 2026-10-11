#!/usr/bin/env python3
#
# This module is used to spawn the gate in container.
# For development purposes use run.sh located outside the package directory.
#

import os
import socket

import uvicorn

from swmcloudgate.tls import uvicorn_ssl_kwargs


def start():
    my_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.dirname(my_dir))
    hostname = socket.gethostname().split(".")[0]
    uvicorn.run(
        "swmcloudgate.main:app",
        log_config=f"{my_dir}/logging.yaml",
        host=hostname,
        port=8444,
        reload=False,
        workers=8,
        limit_concurrency=32,
        limit_max_requests=1000,
        timeout_keep_alive=60,
        **uvicorn_ssl_kwargs(),
    )


if __name__ == "__main__":
    start()
