import datetime
import http
import logging
import traceback
import typing
import uuid

import jinja2
import libcloud.security
import yaml
from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider

from ..baseconnector import BaseConnector

LOG = logging.getLogger("swm")
TEMLPATE_FILE = "app/routers/azure/templates/partition.bicep"
CLOUD_INIT_SCRIPT_FILE = "app/routers/openstack/templates/cloud-init.sh"
SERVICE_NAMES = {"compute": "nova", "orchestration": "heat", "rating": "cloudkitty"}


class AzureConnector(BaseConnector):
    def __init__(self, subscription_id: str, app_id: str, tenant_id: str, password: str):
        self._init_driver(subscription_id, app_id, tenant_id, password)
        super().__init__("azure")

    def reinitialize(self, subscription_id: str, app_id: str, tenant_id: str, password: str) -> None:
        self._init_driver(username, password, service)

    def _init_driver(self, subscription_id: str, app_id: str, tenant_id: str, password: str) -> None:
        # See also https://libcloud.readthedocs.io/en/stable/compute/drivers/azure_arm.html
        subscription_id='3f2fc2c5-8446-4cd5-af2f-a6af7f85ea75',
        app_id = '17e060c4-cb6e-47ac-a881-e55a4782a573',
        tenant_id = 'c8d65d6a-d488-4dd9-9399-68f868316782',
        key_file = '/opt/swm/spool/secure/cluster/private/key.pem',
        if subscription_id and app_id and tenant_id and password:
            https://libcloud.readthedocs.io/en/stable/compute/drivers/azure_arm.html
            AzureDriver = get_driver(Provider.AZURE_ARM)
            LOG.info("Connect to Azure")
            self._driver = AzureDriver(
                tenant_id = tenant_id,
                subscription_id=subscription_id,
                key=app_id,
                key_file=key_file,
            )

    def list_sizes(self) -> list[AzureNodeSize]:
        if "sizes" in self._test_responses:
            node_sizes = []
            for it in self._test_responses["sizes"]:
                node_sizes.append(
                    AzureNodeSize(
                        id=it["id"],
                        name=it["name"],
                        bandwidth=it["bandwidth"],
                        ram=it["ram"],
                        disk=it["disk"],
                        price=it["price"],
                        vcpus=it["vcpus"],
                        ephemeral_disk=it["ephemeral_disk"],
                        swap=it["swap"],
                        driver=self._driver,
                    )
                )
            return node_sizes
        try:
            sizes = self._driver.list_sizes()
            return sizes
        except Exception as e:
            LOG.error(f"Cannot list flavors: {e}")
        return []

    def list_images(self):
        if "images" in self._test_responses:
            node_images = []
            for it in self._test_responses["images"]:
                node_images.append(
                    NodeImage(id=it["id"], name=it["name"], extra={"status": it["status"]}, driver=self._driver)
                )
            return node_images
        return self._driver.list_images()

    def _get_stack_template(
        self,
        stack_name: str,
        image_name: str,
        flavor_name: str,
        key_name: str,
        count: str,
        job_id: str,
        runtime: str,
        ports: str,
    ) -> str:
        template_loader = jinja2.FileSystemLoader(searchpath="./")
        template_env = jinja2.Environment(loader=template_loader, autoescape=True)
        template = template_env.get_template(TEMLPATE_FILE)
        yaml_str = template.render(
            stack_name=stack_name,
            image_name=image_name,
            flavor_name=flavor_name,
            key_name=key_name,
            compute_instances_count=count,
            ingres_tcp_ports=ports.split(","),
            init_script=self._get_cloud_init_script(job_id, runtime),
        )
        return yaml.safe_load(yaml_str)

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

    def _request(
        self,
        action: str,
        method: str,
        data: typing.Any,
        expect: typing.List[int],
    ) -> AzureResponse:
        LOG.debug(f"[REQUEST] {method} {action} {data}")
        response = None
        try:
            response = self._driver.connection.request(action=action, data=data, method=method)
        except libcloud.common.exceptions.BaseHTTPError as e:
            LOG.error(f"HTTP error: {e}")
        if not response:
            return None
        result = response.parse_body()
        status = response.status
        if status not in expect:
            LOG.info(f"Unexpected response status: {status}")
            return None
        LOG.debug(f"[RESPONSE]: {result}")
        return result

    def list_stacks(self) -> typing.List[typing.Dict[str, typing.Any]]:
        if "stacks" in self._test_responses:
            stacks = []
            for it in self._test_responses["stacks"]:
                stacks.append(it)
            return stacks
        result = self._request(action="stacks", method="GET", data={}, expect=[http.client.OK])
        return result.get("stacks", []) if result else []

    def create_deployment(
        self,
        tenant_name: str,
        stack_name: str,
        image_name: str,
        flavor_name: str,
        key_name: str,
        count: str,
        job_id: str,
        runtime: str,
        ports: str,
    ) -> str:
        return {}

    def get_stack(self, stack_id: str) -> typing.Dict[str, typing.Any]:
        return {}

    def delete_stack(self, stack_id: str) -> str:
        return "Deletion started"
