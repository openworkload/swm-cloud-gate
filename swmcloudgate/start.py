#!/usr/bin/env python3
#
# This module is used to spawn the gate in container.
# For development purposes use run.sh located outside the package directory.
#

import os
import ssl
import socket

import uvicorn


def start():
    spool = "/opt/swm/spool/secure"
    my_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(os.path.dirname(my_dir))
    uvicorn.run(
        "swmcloudgate.main:app",
        log_config=f"{my_dir}/swmcloudgate/logging.yaml",
        host=socket.gethostname(),
        port=8444,
        reload=False,
        workers=8,
        limit_concurrency=32,
        limit_max_requests=1000,
        timeout_keep_alive=60,
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
        ssl_ca_certs=os.path.join(spool, "cluster", "cert.pem"),
        ssl_keyfile=os.path.join(spool, "node", "key.pem"),
        ssl_certfile=os.path.join(spool, "node", "cert.pem"),
    )


if __name__ == "__main__":
    start()
