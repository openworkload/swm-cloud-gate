#!/usr/bin/env python3

import os
import socket

import uvicorn

from swmcloudgate.tls import uvicorn_ssl_kwargs


def main():
    my_dir = os.path.dirname(os.path.abspath(__file__))
    # Default to fewer workers so large Azure responses do not OOM small hosts.
    workers = int(os.environ.get("SWM_GATE_WORKERS", "2"))
    # SWM_GATE_HOST overrides bind address (mocked CT uses 127.0.0.1).
    host = os.environ.get("SWM_GATE_HOST") or socket.getfqdn()
    uvicorn.run(
        "swmcloudgate.main:app",
        log_config=f"{my_dir}/swmcloudgate/logging.yaml",
        host=host,
        port=8444,
        reload=False,
        workers=workers,
        limit_concurrency=32,
        limit_max_requests=1000,
        timeout_keep_alive=60,
        **uvicorn_ssl_kwargs(),
    )


if __name__ == "__main__":
    main()
