import json
import logging
import typing

import jinja2
import yaml
from azure.core.exceptions import HttpResponseError
from azure.identity import CertificateCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import VirtualMachineImage, VirtualMachineSize
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.resource.resources.models import DeploymentMode

from ..baseconnector import BaseConnector

LOG = logging.getLogger("swm")
TEMLPATE_FILE = "app/routers/azure/templates/partition.json"
CLOUD_INIT_SCRIPT_FILE = "app/routers/openstack/templates/cloud-init.sh"


class AzureConnector(BaseConnector):
    def __init__(self) -> None:
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
        user_pub_cert_path: str,
    ) -> dict[str, dict[str, typing.Any]]:
        with open(TEMLPATE_FILE) as template_file:
            template = json.load(template_file)
        template_parameters = self._get_template_parameters(
            job_id,
            flavor_name,
            os_version,
            username,
            user_pub_cert_path,
        )
        LOG.debug(f"Template parameters for job {job_id}: {tempalte_parameters}")
        return {
            "properties": {
                "template": template,
                "parameters": template_parameters,
                "mode": DeploymentMode.incremental,
            }
        }

    def _get_template_parameters(
        self,
        job_id: str,
        flavor_name: str,
        os_version: str,
        username: str,
        user_pub_cert_path: str,
    ) -> dict[str, str]:
        return {
            "resourcePrefix": {"value": self._get_resource_prefix(job_id)},
            "adminUsername": {"value": username},
            "adminPasswordOrKey": {"value": self._get_vm_user_public_certificate(user_pub_cert_path)},
            "osVersion": {"value": os_version},
            "vmSize": {"value": flavor_name},
        }

    def _read_template(self, template_path) -> str:
        with open(template_path) as template_file:
            return json.load(template_file)

    def _get_vm_user_public_certificate(self, user_pub_cert_path: str) -> str:
        with open(user_pub_cert_path, "rb") as file:
            pub_cert_content = file.read()
        return pub_cert_content.decode("utf-8")

    def _get_pem_data(self, cert_file_path: str, key_file_path: str) -> str:
        with open(cert_path, "rb") as file:
            cert_content = file.read()
        with open(key_file_path, "rb") as file:
            key_content = file.read()
        return key_content + cert_content

    def _get_resource_prefix(self, job_id: str) -> str:
        return "swm-" + job_id.split("-")[0]

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
                node_images.append(
                    VirtualMachineImage(
                        id=it["id"],
                        name=it["name"],
                        location=it["location"],
                        publichser=it["publisher"],
                        offer=it["offer"],
                        skus=it["skus"],
                        version=it["version"],
                        plan=it["plan"],
                        os_disk_image=it["os_disk_image"],
                        data_disk_images=it["data_disk_images"],
                        automatic_os_upgrade_properties=it["automatic_os_upgrade_properties"],
                        hyper_vgeneration=it["hyper_vgeneration"],
                        features=it["features"],
                    )
                )
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

    def _get_cloud_init_script(self, job_id: str, runtime: str) -> str:
        runtime_params = self._get_runtime_params(runtime)
        template_loader = jinja2.FileSystemLoader(searchpath="./")
        template_env = jinja2.Environment(loader=template_loader, autoescape=True)
        template = template_env.get_template(CLOUD_INIT_SCRIPT_FILE)
        script: str = template.render(
            job_id=job_id,
            swm_source=runtime_params.get("swm_source"),
        )
        return script

    def _get_runtime_params(self, runtime: str) -> dict[str, str]:
        runtime_params: dict[str, str] = {}
        LOG.debug(f"Runtime parameters string: {runtime}")
        for it in runtime.split(","):
            [key, value] = it.split("=")
            runtime_params[key] = value
        LOG.debug(f"Runtime parameters parsed: {runtime_params}")
        return runtime_params

    def list_stacks(self) -> typing.List[typing.Dict[str, typing.Any]]:
        if "stacks" in self._test_responses:
            stacks = []
            for it in self._test_responses["stacks"]:
                stacks.append(it)
            return stacks
        # TODO
        return []

    def create_deployment(
        self,
        job_id: str,
        location: str,
        flavor_name: str,
        os_version: str,
        count: str,
        runtime: str,
        ports: str,
        user_pub_cert_path: str,
    ) -> str:
        # TODO use runtime, count and ports
        resource_prefix = self._get_resource_prefix(job_id)
        resource_group_name = self._get_resource_group_name(resource_prefix)
        resource_group_creation_result = self._resource_client.resource_groups.create_or_update(
            resource_group_name, {"location": location}
        )
        LOG.info(f"Provisioned resource group with ID: {resource_group_creation_result.id}")

        deployment_name = self._get_deployment_name(resource_prefix)
        deployment_properties = self._get_deployment_properties(
            job_id,
            flavor_name,
            os_version,
            username,
            user_pub_cert_path,
        )
        deployment_async_operation = resource_client.deployments.begin_create_or_update(
            resource_group_name,
            deployment_name,
            deployment_properties,
        )
        LOG.info(f"Deploying resource group {resource_group_name}, deployment: {deployment_name}")

        try:
            return deployment_async_operation.result()
        except HttpResponseError as e:
            LOG.error(f"Exception when deploying resources for job {job_id}: {e}")
        return ""

    def get_stack(self, stack_id: str) -> typing.Dict[str, typing.Any]:
        # TODO
        return {}

    def delete_resource_group(self, resource_group_name: str) -> str | None:
        if delete_async_operation := self._resource_client.resource_groups.begin_delete(resource_group_name):
            return "Deletion started"
        return None

    def find_image(
        self, location: str, publisher: str, offer: str, sku: str, version: str
    ) -> VirtualMachineImage | None:
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
