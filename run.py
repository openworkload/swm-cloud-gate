#!/usr/bin/env python3

import os
import socket
import ssl

import uvicorn


def main():
    spool = "/opt/swm/spool/secure"
    uvicorn.run(
        "app.main:app",
        log_config="logging.yaml",
        host=socket.gethostname(),
        port=8444,
        reload=False,
        timeout_keep_alive=60,
        ssl_version=ssl.PROTOCOL_TLS_SERVER,
        ssl_ca_certs=os.path.join(spool, "cluster", "cert.pem"),
        ssl_keyfile=os.path.join(spool, "node", "key.pem"),
        ssl_certfile=os.path.join(spool, "node", "cert.pem"),
    )


if __name__ == "__main__":
    main()
