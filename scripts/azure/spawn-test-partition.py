#!/usr/bin/env python3

import json
import os
import getpass

from azure.core.exceptions import HttpResponseError
from azure.identity import CertificateCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import DeploymentMode

job_id = "02ccc5c0-bbbb-11ee-9b4c-6ba8eb3e6d9c"
resource_prefix = "swm-" + job_id.split("-")[0]
resource_group_name = f'{resource_prefix}-resource-group'
location = 'East US'
deployment_name = f'{resource_prefix}-deployment'
template_path = 'app/routers/azure/templates/partition.json'
cert_path = os.path.expanduser("~/.swm/cert.pem")
key_path = os.path.expanduser("~/.swm/key.pem")
user_pub_cert_path = os.path.expanduser("~/.ssh/id_rsa.pub")
os_version = "Ubuntu-2204-swm"
flavor = "Standard_B2s"
username = getpass.getuser()


def read_env_file(file_path: str = "~/.swm/azure.env") -> dict[str, str]:
    config_dict: dict[str, str] = {}
    with open(os.path.expanduser(file_path), 'r') as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            config_dict[key] = value
    return config_dict


def main():
    conf = read_env_file()
    print(f"Configuration: {conf}")

    with open(user_pub_cert_path, 'rb') as file:
        pub_cert_content = file.read()
    with open(key_path, 'rb') as file:
        key_content = file.read()
    with open(cert_path , 'rb') as file:
        cert_content = file.read()
    cert_data = key_content + cert_content

    template_parameters = {
        "resourcePrefix": {
            "value": resource_prefix
        },
        "adminUsername": {
            "value": username
        },
        "adminPasswordOrKey": {
            "value": pub_cert_content.decode("utf-8")
        },
        "osVersion": {
            "value": os_version
        },
        "vmSize": {
            "value": flavor
        },
    }

    with open(template_path) as template_file:
        template = json.load(template_file)

    tenant_id = conf["TENANT_ID"]
    app_id = conf["APP_ID"]
    credential = CertificateCredential(
        tenant_id=tenant_id,
        client_id=app_id,
        certificate_data=cert_data,
    )

    deployment_properties = {
        "properties": {
            "template": template,
            "parameters": template_parameters,
            "mode": DeploymentMode.incremental,
        }
    }

    subscription_id = conf["SUBSCRIPTION_ID"]
    resource_client = ResourceManagementClient(credential, subscription_id)

    rg_result = resource_client.resource_groups.create_or_update(
        resource_group_name,
        {"location": location}
    )
    print(f"Provisioned resource group with ID: {rg_result.id}")

    deployment_async_operation = resource_client.deployments.begin_create_or_update(
        resource_group_name,
        deployment_name,
        deployment_properties
    )
    print("Deploying resource group ...")

    try:
        result = deployment_async_operation.result()
    except HttpResponseError as e:
        print(f"Exception: {e}")
    else:
        print(f"Result: {result}")


if __name__ == "__main__":
  main()
