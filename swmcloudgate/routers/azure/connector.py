import os
import json
import base64
import typing
import logging

import jinja2
from azure.identity import CertificateCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.commerce import UsageManagementClient
from azure.mgmt.resource import SubscriptionClient, ResourceManagementClient
from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.compute.models import VirtualMachineSize, VirtualMachineImage
from azure.mgmt.resource.resources.models import DeploymentMode, DeploymentExtended

from swmcloudgate import cache

from ..baseconnector import BaseConnector

LOG = logging.getLogger("swm")
TEMLPATE_FILE = "swmcloudgate/routers/azure/templates/partition.json"
CLOUD_INIT_SCRIPT_FILE = "swmcloudgate/routers/azure/templates/cloud-init.sh"
CLOUD_INIT_YAML = "swmcloudgate/routers/azure/templates/cloud-init.yaml"


class AzureConnector(BaseConnector):
    def __init__(self) -> None:
        self._compute_client = None
        self._resource_client = None
        self._commerce_client = None
        self._subscription = None
        self._subscription_id = None
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
        self._subscription_id = subscription_id
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
            self._commerce_client = UsageManagementClient(credential, subscription_id)
            self._subscription = SubscriptionClient(credential).subscriptions.get(subscription_id)
        else:
            LOG.error("Not enough parameters provided to initialize Azure connection")

    def _get_deployment_properties(
        self,
        job_id: str,
        partition_name: str,
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
            partition_name,
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
        partition_name: str,
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
            "resourcePrefix": {"value": partition_name},
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

    def _get_resource_prefix(self) -> str:
        return "swm-"

    def _get_resource_group_name(self, partition_name: str) -> str:
        return f"{partition_name}-resource-group"

    def _get_deployment_name(self, partition_name: str) -> str:
        return f"{partition_name}-deployment"

    def list_sizes(self, location: str) -> list[VirtualMachineSize]:
        if "sizes" in self._test_responses:
            node_sizes = []
            for it in self._test_responses["sizes"]:
                vm_size = VirtualMachineSize(
                    name=it["name"],
                    number_of_cores=it["number_of_cores"],
                    resource_disk_size_in_mb=it["resource_disk_size_in_mb"],
                    memory_in_mb=it["memory_in_mb"],
                )
                vm_size.extra = {"price": it["price"], "description": "test vm size"}
                node_sizes.append(vm_size)
            return node_sizes

        if data := cache.data_cache("flavors", "azure").fetch_and_update([location]):
            LOG.debug(f"Flavors are taken from cache (amount={len(data)})")
            return data

        size_map: dict[str, VirtualMachineSize] = {}
        for size in self._compute_client.virtual_machine_sizes.list(location):
            size_map[size.name] = size
        LOG.debug(f"Retrieved {len(size_map)} flavors from Azure")
        result = self._add_prices(location, size_map)

        changed, deleted = cache.data_cache("flavors", "azure").update([location], result)
        if changed or deleted:
            LOG.debug(f"Flavors cache updated (changed={changed}, deleted={deleted})")

        return result

    def _add_prices(self, location: str, size_map: dict[str, VirtualMachineSize]) -> list[VirtualMachineSize]:
        results: list[VirtualMachineSize] = []

        if self._subscription.subscription_policies.quota_id.lower().startswith("payasyougo"):
            offer_id = "0003P"
        else:
            raise Exception("For now only PayAsYouGo offers are supported")
        filter_string = (
            f"OfferDurableId eq 'MS-AZR-{offer_id}'"
            "and Currency eq 'USD' and Locale eq 'en-US' and RegionInfo eq 'US'"
        )
        LOG.debug(f"Rates filter: {filter_string}")
        meters = self._commerce_client.rate_card.get(filter_string).meters
        LOG.debug(f"Retrieved {len(meters)} meters")

        already_added = set()
        duplication_counter = 1
        for meter in meters:
            if meter.meter_category != "Virtual Machines":
                continue
            if meter.meter_name.endswith("Low Priority"):
                continue
            parts = meter.meter_region.split(" ")
            if len(parts) != 2:
                continue
            location_from_meter = (parts[1] + parts[0]).lower()
            if location != location_from_meter:
                continue
            for meter_name in meter.meter_name.split("/"):
                size_name = f"Standard_{meter_name.replace(' ', '_')}"
                if vm_size := size_map.get(size_name):
                    vm_size.extra = {"price": meter.meter_rates["0"], "description": meter.meter_sub_category}
                    if vm_size.name not in already_added:
                        already_added.add(vm_size.name)
                        results.append(vm_size)
                    else:
                        duplication_counter += 1
        return results

    def list_images(self, location: str, publisher: str, offer: str, skus: str) -> list[VirtualMachineImage]:
        images: list[VirtualMachineImage] = []
        if "images" in self._test_responses:
            for it in self._test_responses["images"]:
                vm_image = VirtualMachineImage(
                    id=it["id"],
                    name=it["name"],
                    location=it["extra"]["location"],
                    publisher=it["extra"]["publisher"],
                    offer=it["extra"]["offer"],
                    skus=it["extra"]["skus"],
                    version=it["extra"]["version"],
                )
                vm_image.extra = {}
                images.append(vm_image)
            return images

        LOG.debug(f"List images: location={location}, publisher={publisher}, offer={offer}, skus={skus}")
        cache_key = [location, publisher, offer, skus] if skus else [location, publisher, offer]
        if data := cache.data_cache("vmimages", "azure").fetch_and_update(cache_key):
            LOG.debug(f"VM images are taken from cache (amount={len(data)})")
            return data

        if skus:
            if azure_image := self._get_latest_sku_image(location, publisher, offer, skus):
                images.append(azure_image)
        else:
            azure_skus = self._compute_client.virtual_machine_images.list_skus(
                location=location,
                publisher_name=publisher,
                offer=offer,
            )
            for sku in azure_skus:
                if azure_image := self._get_latest_sku_image(location, publisher, offer, sku.name):
                    images.append(azure_image)

        changed, deleted = cache.data_cache("vmimages", "azure").update(cache_key, images)
        if changed or deleted:
            LOG.debug(f"VM image cache updated (changed={changed}, deleted={deleted})")

        return images

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
        prefix = self._get_resource_prefix()
        if not resource_group_name.startswith(prefix):
            return None
        try:
            if resource_group := self._resource_client.resource_groups.get(resource_group_name):
                return self._get_resource_group_info(resource_group.id, resource_group.name)
        except ResourceNotFoundError:
            LOG.info(f"Resource group does not exist in Azure: {resource_group_name}")
        return None

    def list_resource_groups(self) -> list[dict[str, typing.Any]]:
        if "resource_groups" in self._test_responses:
            resource_groups = []
            for it in self._test_responses["resource_groups"]:
                resource_groups.append(it)
            return resource_groups
        group_resources: list[dict[str, list[typing.Any]]] = []
        if resource_groups := self._resource_client.resource_groups.list():
            prefix = self._get_resource_prefix()
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
        partition_name: str,
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
    ) -> tuple[DeploymentExtended, str]:
        resource_group_name = self._get_resource_group_name(partition_name)

        if self._test_responses:
            new_part = {
                "id": f"/subscriptions/{self._subscription_id}/resourceGroups/{partition_name}-resource-group",
                "name": resource_group_name,
            }
            self._test_responses.setdefault("resource_groups", []).append(new_part)
            LOG.debug(f"New partition added: {new_part}")
            return new_part, resource_group_name

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

        deployment_name = self._get_deployment_name(partition_name)
        deployment_properties = self._get_deployment_properties(
            job_id,
            partition_name,
            flavor_name,
            os_version,
            username,
            runtime_params.get("ssh_pub_key"),
            cloud_init_script,
            ports,
        )
        try:
            deployment_async_operation = self._resource_client.deployments.begin_create_or_update(
                resource_group_name,
                deployment_name,
                deployment_properties,
            )
        except azure.core.exceptions.HttpResponseError as e:
            LOG.error(e)
            raise e


        LOG.info(f"Deploying resource group {resource_group_name}, deployment: {deployment_name}")
        return deployment_async_operation.result(), resource_group_name

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
                img_id = (
                    f"/Subscriptions/{self._subscription_id}/Providers/Microsoft.Compute/"
                    f"Locations/{location}/Publishers/{publisher}/ArtifactTypes/VMImage/"
                    f"Offers/{offer}/Skus/{sku}/Versions/{version}"
                )
                if img_id == it["id"]:
                    vm_image = VirtualMachineImage(
                        id=img_id,
                        name=it["name"],
                        location=location,
                        publisher=publisher,
                        offer=offer,
                        skus=sku,
                        version=version,
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
