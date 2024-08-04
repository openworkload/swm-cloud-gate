import base64
import datetime
import json
import logging
import os
import typing
import uuid

import jinja2
from azure.identity import CertificateCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import VirtualMachineImage, VirtualMachineSize
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import DeploymentMode

from ..baseconnector import BaseConnector

LOG = logging.getLogger("swm")
TEMLPATE_FILE = "app/routers/azure/templates/partition.json"
CLOUD_INIT_SCRIPT_FILE = "app/routers/azure/templates/cloud-init.sh"
CLOUD_INIT_YAML = "app/routers/azure/templates/cloud-init.yaml"


class AzureConnector(BaseConnector):
    def __init__(self) -> None:
        self._compute_client = None
        self._resource_client = None
        super().__init__("azure")

    def reinitialize(
        self,
        subscription_id: str,
        tenant_id: str,
        app_id: str,
        pem_data: bytes,
    ) -> None:
        self._init_azure_clients(subscription_id, tenant_id, app_id, pem_data)

    def _init_azure_clients(
        self,
        subscription_id: str,
        tenant_id: str,
        app_id: str,
        pem_data: bytes,
    ) -> None:
        if os.getenv("SWM_TEST_CONFIG", None):
            return
        if subscription_id and tenant_id and app_id and len(pem_data):
            credential = CertificateCredential(
                tenant_id=tenant_id,
                client_id=app_id,
                certificate_data=pem_data,
            )
            self._compute_client = ComputeManagementClient(credential, subscription_id)
            self._resource_client = ResourceManagementClient(credential, subscription_id)
        else:
            LOG.error("Not enough parameters provided to initialize Azure connection")

    def _get_deployment_properties(
        self,
        job_id: str,
        flavor_name: str,
        os_version: str,
        username: str,
        user_pub_key: str,
        cloud_init_script: str,
        ports: str,
    ) -> dict[str, dict[str, typing.Any]]:
        with open(TEMLPATE_FILE) as template_file:
            template = json.load(template_file)
        template_parameters = self._get_template_parameters(
            job_id,
            flavor_name,
            os_version,
            username,
            user_pub_key,
            cloud_init_script,
        )
        LOG.debug(f"Template parameters for job {job_id}: {template_parameters}")
        self._append_security_rules(ports, template)
        # self._append_cloud_init_script(cloud_init_script, template)
        return {
            "properties": {
                "template": template,
                "parameters": template_parameters,
                "mode": DeploymentMode.incremental,
            }
        }

    def _append_security_rules(self, ports: str, template: dict[str, typing.Any]) -> None:
        for resource in template["resources"]:
            if resource["type"] == "Microsoft.Network/networkSecurityGroups":
                for counter, port in enumerate(ports.split(",")):
                    rule = {
                        "name": f"swm-port-{port}",
                        "properties": {
                            "priority": 1001 + counter,
                            "protocol": "Tcp",
                            "access": "Allow",
                            "direction": "Inbound",
                            "sourceAddressPrefix": "*",
                            "sourcePortRange": "*",
                            "destinationAddressPrefix": "*",
                            "destinationPortRange": port,
                        },
                    }
                    LOG.debug(f"Add security group rule: {rule}")
                    resource["properties"]["securityRules"].append(rule)

    def _append_cloud_init_script(self, cloud_init_script: str, template: str) -> None:
        cloud_init_yaml = f"#cloud-config\nruncmd: |+\n{self._indent_lines(cloud_init_script, 4)}"
        encoded = base64.b64encode(cloud_init_yaml.encode("utf-8"))
        template["variables"]["cloudInit"] = f"[base64('{encoded}')]"

    def _indent_lines(self, text: str, indentation: int) -> str:
        lines = text.split("\n")
        indented_lines = [" " * indentation + line for line in lines]
        return "\n".join(indented_lines)

    def _get_template_parameters(
        self,
        job_id: str,
        flavor_name: str,
        os_version: str,
        username: str,
        user_pub_key: str,
        cloud_init_script: str,
    ) -> dict[str, str]:
        template_loader = jinja2.FileSystemLoader(searchpath="./")
        template_env = jinja2.Environment(loader=template_loader, autoescape=False)  # nosec B701
        template = template_env.get_template(CLOUD_INIT_YAML)
        cloud_init_yaml: str = template.render(
            cloud_init_script=self._indent_lines(cloud_init_script, 6),
        )
        return {
            "resourcePrefix": {"value": self._get_resource_prefix(job_id)},
            "adminUsername": {"value": username},
            "adminPasswordOrKey": {"value": user_pub_key},
            "osVersion": {"value": os_version},
            "vmSize": {"value": flavor_name},
            "cloudInitScript": {"value": cloud_init_yaml},
        }

    def _read_template(self, template_path) -> str:
        with open(template_path) as template_file:
            return json.load(template_file)

    def _get_pem_data(self, cert_file_path: str, key_file_path: str) -> str:
        with open(cert_file_path, "rb") as file:
            cert_content = file.read()
        with open(key_file_path, "rb") as file:
            key_content = file.read()
        return key_content + cert_content

    def _get_resource_prefix_no_job_id(self) -> str:
        return "swm-"

    def _get_resource_prefix(self, job_id: str) -> str:
        return self._get_resource_prefix_no_job_id() + job_id.split("-")[0]

    def _get_resource_group_name(self, resource_prefix: str) -> str:
        return f"{resource_prefix}-resource-group"

    def _get_deployment_name(self, resource_prefix: str) -> str:
        return f"{resource_prefix}-deployment"

    def list_sizes(self, location: str) -> list[VirtualMachineSize]:
        if "sizes" in self._test_responses:
            node_sizes = []
            for it in self._test_responses["sizes"]:
                node_sizes.append(
                    VirtualMachineSize(
                        name=it["name"],
                        number_of_cores=it["number_of_cores"],
                        os_disk_size_in_mb=it["os_disk_size_in_mb"],
                        resource_disk_size_in_mb=it["resource_disk_size_in_mb"],
                        memory_in_mb=it["memory_in_mb"],
                        max_data_disk_count=it["max_data_disk_count"],
                    )
                )
            return node_sizes
        return list(self._compute_client.virtual_machine_sizes.list(location))

    def list_images(self, location: str, publisher: str, offer: str, skus: str) -> list[VirtualMachineImage]:
        node_images: list[VirtualMachineImage] = []
        if "images" in self._test_responses:
            for it in self._test_responses["images"]:
                vm_image = VirtualMachineImage(
                    id=it["id"],
                    name=it["name"],
                    location=it["location"],
                    publisher=it["publisher"],
                    offer=it["offer"],
                    skus=it["skus"],
                    version=it["version"],
                )
                vm_image.extra = {}
                node_images.append(vm_image)
            return node_images
        LOG.debug(f"List images: location={location}, publisher={publisher}, offer={offer}, skus={skus}")
        if skus:
            if azure_image := self._get_latest_sku_image(location, publisher, offer, skus):
                node_images.append(azure_image)
        else:
            azure_skus = self._compute_client.virtual_machine_images.list_skus(
                location=location,
                publisher_name=publisher,
                offer=offer,
            )
            for sku in azure_skus:
                if azure_image := self._get_latest_sku_image(location, publisher, offer, sku.name):
                    node_images.append(azure_image)
        return node_images

    def _get_latest_sku_image(self, location: str, publisher: str, offer: str, sku: str) -> VirtualMachineImage | None:
        max_date_image: VirtualMachineImage | None = None
        max_date = ""
        for azure_image in self._compute_client.virtual_machine_images.list(
            location=location,
            publisher_name=publisher,
            offer=offer,
            skus=sku,
        ):
            if azure_image.name > max_date:
                max_date_image = azure_image
        if max_date_image:
            max_date_image.extra: dict[str, str] = {"sku": sku, "publisher": publisher, "offer": offer}
        return max_date_image

    def _get_cloud_init_script(
        self,
        job_id: str,
        container_image: str,
        container_registry: str,
        container_registry_username: str,
        container_registry_password: str,
        runtime_params: str,
    ) -> str:
        template_loader = jinja2.FileSystemLoader(searchpath="./")
        template_env = jinja2.Environment(loader=template_loader, autoescape=True)
        template = template_env.get_template(CLOUD_INIT_SCRIPT_FILE)
        script: str = template.render(
            job_id=job_id,
            swm_source=runtime_params.get("swm_source"),
            ssh_pub_key=runtime_params.get("ssh_pub_key"),
            container_image=container_image,
            container_registry=container_registry,
            container_registry_username=container_registry_username,
            container_registry_password=container_registry_password,
        )
        return script

    def get_resource_group(self, resource_group_name: str) -> typing.Dict[str, typing.Any]:
        if "resource_groups" in self._test_responses:
            for it in self.list_resource_groups():
                if it["name"] == resource_group_name:
                    return it
            return {}
        prefix = self._get_resource_prefix_no_job_id()
        if not resource_group_name.startswith(prefix):
            return None
        if resource_group := self._resource_client.resource_groups.get(resource_group_name):
            return self._get_resource_group_info(resource_group.id, resource_group.name)
        return None

    def list_resource_groups(self) -> list[dict[str, typing.Any]]:
        if "resource_groups" in self._test_responses:
            resource_groups = []
            for it in self._test_responses["resource_groups"]:
                resource_groups.append(it)
            return resource_groups
        group_resources: list[dict[str, list[typing.Any]]] = []
        if resource_groups := self._resource_client.resource_groups.list():
            prefix = self._get_resource_prefix_no_job_id()
            for resource_group in resource_groups:
                if not resource_group.name.startswith(prefix):
                    continue
                if info := self._get_resource_group_info(resource_group.id, resource_group.name):
                    group_resources.append(info)
        return group_resources

    def _get_resource_group_info(self, id: str, name: str) -> dict[str, list[typing.Any]]:
        resource_group_info: dict[str, list[typing.Any]] = {
            "resources": [],
            "id": id,
            "name": name,
        }
        if resources := self._resource_client.resources.list_by_resource_group(
            name, expand="properties,createdTime,changedTime"
        ):
            for resource in resources:
                if resource.type in [
                    "Microsoft.Network/publicIPAddresses",
                    "Microsoft.Network/networkInterfaces",
                ]:  # We need extended properties for those resources
                    if extended_resource := self._resource_client.resources.get_by_id(
                        resource.id, api_version="2019-02-01"
                    ):
                        resource_group_info["resources"].append(extended_resource)
                        continue
                resource_group_info["resources"].append(resource)
        return resource_group_info

    def create_deployment(
        self,
        job_id: str,
        os_version: str,
        container_image: str,
        container_registry_username: str,
        container_registry_password: str,
        flavor_name: str,
        username: str,
        count: str,
        runtime: str,
        location: str,
        ports: str,
    ) -> str:
        resource_prefix = self._get_resource_prefix(job_id)
        resource_group_name = self._get_resource_group_name(resource_prefix)

        if self._test_responses:
            id = str(uuid.uuid4())
            time = datetime.datetime.now().isoformat()
            new_part = {
                "id": id,
                "name": resource_group_name,
            }
            self._test_responses.setdefault("resource_groups", []).append(new_part)
            return {"id": id, "name": resource_group_name}

        resource_group_creation_result = self._resource_client.resource_groups.create_or_update(
            resource_group_name, {"location": location}
        )
        LOG.info(f"Provisioned resource group with ID: {resource_group_creation_result.id}")

        runtime_params = self._get_runtime_params(runtime)
        container_registry = container_image.split("/")[0]
        cloud_init_script: str = self._get_cloud_init_script(
            job_id,
            container_image,
            container_registry,
            container_registry_username,
            container_registry_password,
            runtime_params,
        )

        deployment_name = self._get_deployment_name(resource_prefix)
        deployment_properties = self._get_deployment_properties(
            job_id,
            flavor_name,
            os_version,
            username,
            runtime_params.get("ssh_pub_key"),
            cloud_init_script,
            ports,
        )
        deployment_async_operation = self._resource_client.deployments.begin_create_or_update(
            resource_group_name,
            deployment_name,
            deployment_properties,
        )

        LOG.info(f"Deploying resource group {resource_group_name}, deployment: {deployment_name}")
        return deployment_async_operation.result()

    def delete_resource_group(self, resource_group_name: str) -> str | None:
        if "resource_groups" in self._test_responses:
            for it in self.list_resource_groups():
                if it["name"] == resource_group_name:
                    return "Deletion started"
            return None
        if self._resource_client.resource_groups.begin_delete(resource_group_name):
            return "Deletion started"
        return None

    def find_image(
        self, location: str, publisher: str, offer: str, sku: str, version: str
    ) -> VirtualMachineImage | None:
        if "images" in self._test_responses:
            for it in self._test_responses["images"]:
                if (
                    it["location"] == location
                    and it["publisher"] == publisher
                    and it["offer"] == offer
                    and it["skus"] == sku
                    and it["version"] == version
                ):
                    vm_image = VirtualMachineImage(
                        id=it["id"],
                        name=it["name"],
                        location=it["location"],
                        publisher=it["publisher"],
                        offer=it["offer"],
                        skus=it["skus"],
                        version=it["version"],
                    )
                    vm_image.extra = {}
                    return vm_image
            return {}
        if azure_image := self._compute_client.virtual_machine_images.get(
            location=location,
            publisher_name=publisher,
            offer=offer,
            skus=sku,
            version=version,
        ):
            azure_image.extra: dict[str, str] = {"sku": sku, "publisher": publisher, "offer": offer, "version": version}
            return azure_image
        return None
