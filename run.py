#!/usr/bin/env python3

import os
import socket

import uvicorn

if __name__ == "__main__":
    spool = "/opt/swm/spool/secure"
    uvicorn.run(
        "app.main:app",
        log_config=None,  # custom logger will be used
        host=socket.gethostname(),
        port=8444,
        reload=True,
        log_level="debug",
        timeout_keep_alive=60,
        ssl_ca_certs=os.path.join(spool, "cluster", "cert.pem"),
        ssl_keyfile=os.path.join(spool, "node", "key.pem"),
        ssl_certfile=os.path.join(spool, "node", "cert.pem"),
    )

# https://mydeveloperplanet.com/2020/03/11/how-to-mock-a-rest-api-in-python/
# https://requests-mock.readthedocs.io/en/latest/overview.html
# http://empt1e.blogspot.com/2011/02/mocking-libcloud-using-mox.html
