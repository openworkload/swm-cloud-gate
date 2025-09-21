#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: © 2021 Taras Shapovalov
# SPDX-License-Identifier: BSD-3-Clause
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
# list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
# this list of conditions and the following disclaimer in the documentation
# and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holder nor the names of its
# contributors may be used to endorse or promote products derived from
# this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#

import os
import ssl
import socket
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager

import config

SWM_SPOOL = os.getenv("SWM_SPOOL", (Path.home() / ".swm/spool").as_posix())
CERT = f"{SWM_SPOOL}/secure/node/cert.pem"
KEY = f"{SWM_SPOOL}/secure/node/key.pem"
CA = f"{SWM_SPOOL}/secure/cluster/ca-chain-cert.pem"

HOST = socket.getfqdn()
PORT = 8444


def make_pem_data(cert_path: str, key_path: str) -> str:
    with open(key_path, "r") as key_file:
        content1 = key_file.read()
    cert_lines = []
    inside_cert = False
    with open(cert_path, "r") as cert_file:
        for line in cert_file:
            if "-----BEGIN CERTIFICATE-----" in line:
                inside_cert = True
            if inside_cert:
                cert_lines.append(line)
            if "-----END CERTIFICATE-----" in line:
                inside_cert = False
    content2 = "".join(cert_lines)
    joined_content = content1 + content2
    return joined_content


def main() -> None:

    settings = config.get_settings()

    subscription_id = settings.providers.azure.api_credentials.subscription_id
    tenant_id = settings.providers.azure.api_credentials.tenant_id
    app_id = settings.providers.azure.api_credentials.app_id

    publisher = settings.providers.azure.vm_image.publisher
    offer = settings.providers.azure.vm_image.offer

    pem_data = make_pem_data(CERT, KEY)

    try:
        list_flavors(subscription_id, tenant_id, app_id, pem_data)
        list_images(subscription_id, tenant_id, app_id, publisher, offer, pem_data)
    except requests.exceptions.SSLError as e:
        print(f"\nERROR: {e}")


class TLS13Adapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = ssl.create_default_context()
        self.poolmanager = PoolManager(*args, ssl_context=ctx, **kwargs)


def list_flavors(subscription_id: str, tenant_id: str, app_id: str, pem_data: str) -> None:
    url = f"https://{HOST}:{PORT}/azure/flavors"
    headers = {
        "Accept": "application/json",
        "subscriptionid": subscription_id,
        "tenantid": tenant_id,
        "appid": app_id,
        "extra": "location=eastus",
    }
    body = {"pem_data": pem_data}

    session = requests.Session()
    session.mount("https://", TLS13Adapter())
    response = session.get(
        url,
        headers=headers,
        json=body,
        cert=(CERT, KEY),
        verify=CA,
    )

    response.raise_for_status()
    json_data = response.json()
    print(f"Cached {len(json_data.get('flavors', []))} VM flavors")


def list_images(
    subscription_id: str,
    tenant_id: str,
    app_id: str,
    publisher: str,
    offer: str,
    pem_data: str,
) -> None:
    url = f"https://{HOST}:{PORT}/azure/images"
    headers = {
        "Accept": "application/json",
        "subscriptionid": subscription_id,
        "tenantid": tenant_id,
        "appid": app_id,
        "extra": f"location=eastus;publisher={publisher};offer={offer}",
    }
    body = {"pem_data": pem_data}

    session = requests.Session()
    session.mount("https://", TLS13Adapter())
    response = session.get(
        url,
        headers=headers,
        json=body,
        cert=(CERT, KEY),
        verify=CA,
    )
    response.raise_for_status()
    json_data = response.json()
    print(f"Cached {len(json_data.get('images', []))} VM images")


if __name__ == "__main__":
    main()
