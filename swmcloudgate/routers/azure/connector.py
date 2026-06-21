import os
import json
import copy
import typing
import logging

import jinja2
from azure.identity import CertificateCredential
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.commerce import UsageManagementClient
from azure.mgmt.resource import SubscriptionClient, ResourceManagementClient
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError
from azure.mgmt.compute.models import VirtualMachineSize, VirtualMachineImage
from azure.mgmt.resource.resources.models import DeploymentMode, DeploymentExtended

from swmcloudgate import cache

from ..baseconnector import BaseConnector

LOG = logging.getLogger("swm")
TEMLPATE_FILE = "swmcloudgate/routers/azure/templates/partition.json"
CLOUD_INIT_SCRIPT_FILE = "swmcloudgate/routers/azure/templates/cloud-init.sh"
CLOUD_INIT_YAML = "swmcloudgate/routers/azure/templates/cloud-init.yaml"
MAX_VM_COUNT = 32
HOST_NAME_PLACEHOLDER = "__SWM_HOST_NAME__"
IS_MAIN_PLACEHOLDER = "__SWM_IS_MAIN__"
MAIN_INSTANCE_HOSTNAME_PLACEHOLDER = "__SWM_MAIN_INSTANCE_HOSTNAME__"
MAIN_INSTANCE_PRIVATE_IP_PLACEHOLDER = "__SWM_MAIN_INSTANCE_PRIVATE_IP__"


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
            msg = (
                "Not enough parameters provided to initialize Azure connection:"
                f"{subscription_id}, {tenant_id}, {app_id}, {len(pem_data)}"
            )
            raise Exception(msg)

    def _parse_vm_count(self, count_param: str) -> int:
        """Parse and validate VM count parameter."""
        if count_param is None or count_param == "":
            return 1
        try:
            vm_count = int(count_param)
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid VM count '{count_param}': must be an integer") from exc

        if vm_count < 1:
            raise ValueError(f"Invalid VM count {vm_count}: must be greater than or equal to 1")
        if vm_count > MAX_VM_COUNT:
            raise ValueError(f"Invalid VM count {vm_count}: maximum supported count is {MAX_VM_COUNT}")
        return vm_count

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
        vm_count: int,
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
        self._configure_main_vm_custom_data(template)
        self._add_compute_vms(partition_name, vm_count, template)
        return {
            "properties": {
                "template": template,
                "parameters": template_parameters,
                "mode": DeploymentMode.incremental,
            }
        }

    def _find_resource(
        self, resources: list[dict[str, typing.Any]], resource_type: str
    ) -> dict[str, typing.Any] | None:
        for resource in resources:
            if resource.get("type") == resource_type:
                return resource
        return None

    def _find_vm_extension_resources(self, resources: list[dict[str, typing.Any]]) -> list[dict[str, typing.Any]]:
        return [
            resource for resource in resources if resource.get("type") == "Microsoft.Compute/virtualMachines/extensions"
        ]

    def _get_main_vm_private_ip_expression(self) -> str:
        return (
            "reference(resourceId('Microsoft.Network/networkInterfaces', variables('networkInterfaceName')), "
            "'2021-05-01').ipConfigurations[0].properties.privateIPAddress"
        )

    def _build_vm_custom_data(
        self,
        vm_name_expression: str,
        is_main: bool,
    ) -> str:
        custom_data_expression = "parameters('cloudInitScript')"
        replacements = (
            (HOST_NAME_PLACEHOLDER, vm_name_expression),
            (IS_MAIN_PLACEHOLDER, "'true'" if is_main else "'false'"),
            (MAIN_INSTANCE_HOSTNAME_PLACEHOLDER, "parameters('vmNameMain')"),
            (MAIN_INSTANCE_PRIVATE_IP_PLACEHOLDER, self._get_main_vm_private_ip_expression()),
        )
        for placeholder, replacement in replacements:
            custom_data_expression = f"replace({custom_data_expression}, '{placeholder}', {replacement})"
        return f"[base64({custom_data_expression})]"

    def _configure_main_vm_custom_data(self, template: dict[str, typing.Any]) -> None:
        resources = template.get("resources", [])
        main_vm_resource = self._find_resource(resources, "Microsoft.Compute/virtualMachines")
        if not main_vm_resource:
            LOG.warning("Could not find main VM resource in template")
            return
        main_vm_resource["properties"]["osProfile"]["customData"] = self._build_vm_custom_data(
            "parameters('vmNameMain')",
            is_main=True,
        )

    def _append_dependency(self, resource: dict[str, typing.Any], dependency: str) -> None:
        depends_on = resource.setdefault("dependsOn", [])
        if dependency not in depends_on:
            depends_on.append(dependency)

    def _remove_dependency(self, resource: dict[str, typing.Any], dependency: str) -> None:
        depends_on = resource.get("dependsOn", [])
        resource["dependsOn"] = [item for item in depends_on if item != dependency]

    def _replace_vm_reference(self, value: typing.Any, compute_vm_name: str) -> typing.Any:
        if isinstance(value, str):
            return value.replace("parameters('vmNameMain')", f"'{compute_vm_name}'")
        if isinstance(value, list):
            return [self._replace_vm_reference(item, compute_vm_name) for item in value]
        if isinstance(value, dict):
            return {key: self._replace_vm_reference(item, compute_vm_name) for key, item in value.items()}
        return value

    def _strip_public_ip(self, nic_resource: dict[str, typing.Any]) -> None:
        ip_configurations = nic_resource.get("properties", {}).get("ipConfigurations", [])
        if not ip_configurations:
            return
        ip_configuration_properties = ip_configurations[0].get("properties", {})
        ip_configuration_properties.pop("publicIPAddress", None)

    def _clone_compute_nic(
        self,
        network_interface_resource: dict[str, typing.Any],
        compute_nic_name: str,
    ) -> dict[str, typing.Any]:
        compute_nic_resource = copy.deepcopy(network_interface_resource)
        compute_nic_resource["name"] = f"[format('{compute_nic_name}')]"
        self._strip_public_ip(compute_nic_resource)
        public_ip_dependency = "[resourceId('Microsoft.Network/publicIPAddresses', variables('publicIPAddressName'))]"
        self._remove_dependency(compute_nic_resource, public_ip_dependency)
        return compute_nic_resource

    def _clone_compute_vm(
        self,
        main_vm_resource: dict[str, typing.Any],
        compute_vm_name: str,
        compute_nic_name: str,
    ) -> dict[str, typing.Any]:
        compute_vm_resource = copy.deepcopy(main_vm_resource)
        compute_vm_resource["name"] = f"[format('{compute_vm_name}')]"
        compute_vm_resource["properties"]["networkProfile"]["networkInterfaces"][0][
            "id"
        ] = f"[resourceId('Microsoft.Network/networkInterfaces', '{compute_nic_name}')]"
        compute_vm_resource["properties"]["osProfile"]["computerName"] = f"[format('{compute_vm_name}')]"
        compute_vm_resource["properties"]["osProfile"]["customData"] = self._build_vm_custom_data(
            f"'{compute_vm_name}'",
            is_main=False,
        )
        compute_nic_dependency = f"[resourceId('Microsoft.Network/networkInterfaces', '{compute_nic_name}')]"
        self._append_dependency(compute_vm_resource, compute_nic_dependency)
        return compute_vm_resource

    def _clone_compute_vm_extension(
        self,
        extension_resource: dict[str, typing.Any],
        compute_vm_name: str,
    ) -> dict[str, typing.Any]:
        compute_extension_resource = copy.deepcopy(extension_resource)
        compute_extension_resource = self._replace_vm_reference(compute_extension_resource, compute_vm_name)
        extension_name = extension_resource.get("name", "")
        if "variables('extensionName')" in extension_name:
            compute_extension_resource["name"] = f"[format('{compute_vm_name}/{{0}}', variables('extensionName'))]"
        compute_vm_dependency = f"[resourceId('Microsoft.Compute/virtualMachines', '{compute_vm_name}')]"
        original_vm_dependency = "[resourceId('Microsoft.Compute/virtualMachines', parameters('vmNameMain'))]"
        self._append_dependency(compute_extension_resource, compute_vm_dependency)
        self._remove_dependency(compute_extension_resource, original_vm_dependency)
        return compute_extension_resource

    def _add_compute_vms(
        self,
        partition_name: str,
        vm_count: int,
        template: dict[str, typing.Any],
    ) -> None:
        """Add compute VMs and related resources to the template if vm_count > 1."""
        if vm_count <= 1:
            return

        num_compute_vms = vm_count - 1
        LOG.debug(f"Adding {num_compute_vms} compute VMs to partition {partition_name}")

        resources = template.get("resources", [])
        main_vm_resource = self._find_resource(resources, "Microsoft.Compute/virtualMachines")
        if not main_vm_resource:
            LOG.warning("Could not find main VM resource in template")
            return

        network_interface_resource = self._find_resource(resources, "Microsoft.Network/networkInterfaces")
        if not network_interface_resource:
            LOG.warning("Could not find network interface resource in template")
            return

        extension_resources = self._find_vm_extension_resources(resources)

        for i in range(num_compute_vms):
            compute_index = i + 1
            compute_vm_name = f"{partition_name}-compute{compute_index}"
            compute_nic_name = f"{partition_name}-compute{compute_index}-NetInt"

            compute_nic_resource = self._clone_compute_nic(network_interface_resource, compute_nic_name)
            resources.append(compute_nic_resource)

            compute_vm_resource = self._clone_compute_vm(main_vm_resource, compute_vm_name, compute_nic_name)
            resources.append(compute_vm_resource)

            for extension_resource in extension_resources:
                compute_extension_resource = self._clone_compute_vm_extension(extension_resource, compute_vm_name)
                resources.append(compute_extension_resource)

            LOG.debug(f"Added compute VM {compute_vm_name} to template")

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
                vm_size.extra = {"gpus": 0, "price": it["price"], "description": "test vm size"}
                node_sizes.append(vm_size)
            return node_sizes

        if data := cache.data_cache("flavors", "azure").fetch_and_update([location]):
            LOG.debug(f"Flavors are taken from cache (amount={len(data)})")
            return data

        size_map: dict[str, VirtualMachineSize] = {}
        for size in self._compute_client.virtual_machine_sizes.list(location):
            size.extra: dict[str, str] = {}
            size_map[size.name] = size
        LOG.debug(f"Retrieved {len(size_map)} flavors from Azure")
        self._add_gpus(location, size_map)
        result = self._add_prices(location, size_map)

        changed, deleted = cache.data_cache("flavors", "azure").update([location], result)
        if changed or deleted:
            LOG.debug(f"Flavors cache updated (changed={changed}, deleted={deleted})")

        return result

    def _add_gpus(self, location: str, size_map: dict[str, VirtualMachineSize]) -> None:
        LOG.debug("Retrieve GPU flavors information from Azure")
        skus = self._compute_client.resource_skus.list()
        for sku in skus:
            if sku.resource_type.lower() != "virtualmachines":
                continue
            if sku.name not in size_map.keys():
                continue
            location_from_sku = sku.locations[0] if sku.locations else "Unknown"
            if location != location_from_sku:
                continue
            if gpu_count := next((int(c.value) for c in sku.capabilities if c.name.lower() == "gpus"), 0):
                size_map[sku.name].extra["gpus"] = gpu_count

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
            if len(parts) == 1:
                location_from_meter = parts[0]
            elif len(parts) >= 2:
                location_from_meter = parts[1] + parts[0]
            else:
                continue
            if len(parts) == 3:
                location_from_meter += parts[2]
            if location != location_from_meter.lower():
                continue
            for meter_name in meter.meter_name.split("/"):
                size_name = f"Standard_{meter_name.replace(' ', '_')}"
                if vm_size := size_map.get(size_name):
                    vm_size.extra["price"] = meter.meter_rates["0"]
                    vm_size.extra["description"] = meter.meter_sub_category
                    if vm_size.name not in already_added:
                        already_added.add(vm_size.name)
                        results.append(vm_size)
                    else:
                        duplication_counter += 1
        LOG.debug(f"Number of final flavors: {len(results)}")
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
        storage_account: str,
        storage_key: str,
        storage_container: str,
        runtime_params: str,
        user_ssh_cert: str,
    ) -> str:
        template_loader = jinja2.FileSystemLoader(searchpath="./")
        template_env = jinja2.Environment(loader=template_loader, autoescape=True)
        template = template_env.get_template(CLOUD_INIT_SCRIPT_FILE)
        script: str = template.render(
            job_id=job_id,
            swm_source=runtime_params.get("swm_source"),
            ssh_pub_key=user_ssh_cert,
            container_image=container_image,
            container_registry=container_registry,
            container_registry_username=container_registry_username,
            container_registry_password=container_registry_password,
            storage_account=storage_account,
            storage_key=storage_key,
            storage_container=storage_container,
            host_name=HOST_NAME_PLACEHOLDER,
            is_main=IS_MAIN_PLACEHOLDER,
            main_instance_hostname=MAIN_INSTANCE_HOSTNAME_PLACEHOLDER,
            main_instance_private_ip=MAIN_INSTANCE_PRIVATE_IP_PLACEHOLDER,
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
        storage_account: str,
        storage_key: str,
        storage_container: str,
        flavor_name: str,
        username: str,
        count: str,
        runtime: str,
        location: str,
        ports: str,
        user_ssh_cert: str,
    ) -> tuple[DeploymentExtended, str]:
        resource_group_name = self._get_resource_group_name(partition_name)
        vm_count = self._parse_vm_count(count)
        LOG.info(f"Creating deployment with {vm_count} VM(s)")

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
            storage_account,
            storage_key,
            storage_container,
            runtime_params,
            user_ssh_cert,
        )

        deployment_name = self._get_deployment_name(partition_name)
        deployment_properties = self._get_deployment_properties(
            job_id,
            partition_name,
            flavor_name,
            os_version,
            username,
            user_ssh_cert,
            cloud_init_script,
            ports,
            vm_count,
        )
        try:
            deployment_async_operation = self._resource_client.deployments.begin_create_or_update(
                resource_group_name,
                deployment_name,
                deployment_properties,
            )
        except HttpResponseError as e:
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
