import http
import uuid
import typing
import logging
import datetime
import traceback

import yaml
import jinja2
import libcloud.security
from libcloud.compute.base import NodeImage
from libcloud.compute.types import Provider
from libcloud.common.openstack import OpenStackResponse
from libcloud.compute.providers import get_driver
from libcloud.compute.drivers.openstack import OpenStackNodeSize

from ..baseconnector import BaseConnector

LOG = logging.getLogger("swm")
STACK_TEMLPATE_FILE = "swmcloudgate/routers/openstack/templates/heat_stack.yaml"
CLOUD_INIT_SCRIPT_FILE = "swmcloudgate/routers/openstack/templates/cloud-init.sh"
SERVICE_NAMES = {"compute": "nova", "orchestration": "heat", "rating": "cloudkitty"}


class OpenStackConnector(BaseConnector):
    def __init__(self, username: str = None, password: str = None, service: str = None):
        self._init_driver(username, password, service)
        super().__init__("openstack")

    def reinitialize(self, username: str, password: str, service: str) -> None:
        self._init_driver(username, password, service)

    def _init_driver(self, username: str, password: str, service: str) -> None:
        # See also https://libcloud.readthedocs.io/en/stable/compute/drivers/openstack.html
        if username and password and service:
            libcloud.security.VERIFY_SSL_CERT = False
            OpenStack = get_driver(Provider.OPENSTACK)
            url = "http://172.28.128.254:5000"
            LOG.info(f"Connect to OpenStack: {url}")
            self._driver = OpenStack(
                username,
                password,
                ex_tenant_name="demo1",
                ex_domain_name="Default",
                ex_force_service_type=service,
                ex_force_service_name=SERVICE_NAMES[service],
                ex_force_auth_url=url,
                ex_force_auth_version="3.x_password",
            )

    def list_sizes(self):
        if "sizes" in self._test_responses:
            node_sizes = []
            for it in self._test_responses["sizes"]:
                node_sizes.append(
                    OpenStackNodeSize(
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
        return None

    def list_images(self):
        if "images" in self._test_responses:
            node_images = []
            for it in self._test_responses["images"]:
                node_images.append(
                    NodeImage(
                        id=it["id"], name=it["name"], extra={"status": it["extra"]["status"]}, driver=self._driver
                    )
                )
            return node_images
        return self._driver.list_images()

    def find_image(self, image_id: str):
        images = self.list_images()
        found = [it for it in images if it.id == image_id]
        if found:
            return found[0]
        return None

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
        container_image: str,
    ) -> str:
        template_loader = jinja2.FileSystemLoader(searchpath="./")
        template_env = jinja2.Environment(loader=template_loader, autoescape=True)
        template = template_env.get_template(STACK_TEMLPATE_FILE)
        yaml_str = template.render(
            stack_name=stack_name,
            image_name=image_name,
            flavor_name=flavor_name,
            key_name=key_name,
            compute_instances_count=count,
            ingres_tcp_ports=ports.split(","),
            init_script=self._get_cloud_init_script(job_id, runtime, container_image),
        )
        return yaml.safe_load(yaml_str)

    def _get_cloud_init_script(self, job_id: str, runtime: str, contianer_image: str) -> str:
        runtime_params = self._get_runtime_params(runtime)
        template_loader = jinja2.FileSystemLoader(searchpath="./")
        template_env = jinja2.Environment(loader=template_loader, autoescape=True)
        template = template_env.get_template(CLOUD_INIT_SCRIPT_FILE)
        script: str = template.render(
            job_id=job_id,
            swm_source=runtime_params.get("swm_source"),
            ssh_pub_key=runtime_params.get("ssh_pub_key"),
            container_image=contianer_image,
        )
        return script

    def _request(
        self,
        action: str,
        method: str,
        data: typing.Any,
        expect: typing.List[int],
    ) -> OpenStackResponse:
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

    def create_stack(
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
        container_image: str,
    ) -> str:
        if self._test_responses:
            id = str(uuid.uuid4())
            time = datetime.datetime.now().isoformat()
            new_stack = {
                "id": id,
                "stack_name": stack_name,
                "creation_time": time,
                "updated_time": time,
                "stack_status": "created",
                "description": "test stack",
            }
            self._test_responses.setdefault("stacks", []).append(new_stack)
            return {"id": id, "links": []}
        try:
            template = self._get_stack_template(
                stack_name,
                image_name,
                flavor_name,
                key_name,
                count,
                job_id,
                runtime,
                ports,
                container_image,
            )
        except Exception as e:
            LOG.error(f"Cannot read stack template: {e}, {traceback.format_exc()}")
            return {}
        LOG.debug("Heat stack template has been loaded")
        result = self._request(action="stacks", method="POST", data=template, expect=[http.client.CREATED])
        return result.get("stack", {}) if result else {}

    def get_stack(self, stack_id: str) -> typing.Dict[str, typing.Any]:
        if "stacks" in self._test_responses:
            for it in self.list_stacks():
                if it["id"] == stack_id:
                    return it
            return {}
        stacks = self.list_stacks()  # libcloud (tested on 1.7.0) fails to parse output if stack does not exist
        if list(filter(lambda stack: stack.get("id") == stack_id or stack.get("stack_name") == stack_id, stacks)):
            stack_info = self._request(action=f"stacks/{stack_id}", method="GET", data={}, expect=[http.client.OK])
            return stack_info.get("stack", None) if stack_info else {}
        return {}

    def delete_stack(self, stack_id: str) -> str:
        stack = self.get_stack(stack_id)
        if not stack:
            return f"Stack with id {stack_id} not found"
        if self._test_responses:
            for it in self._test_responses["stacks"]:
                if it["id"] == stack_id:
                    self._test_responses["stacks"].remove(it)
                    break
        else:
            action = f'stacks/{stack["stack_name"]}/{stack_id}'
            self._request(action=action, method="DELETE", data={}, expect=[http.client.NO_CONTENT])
        return "Deletion started"
