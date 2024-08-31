import os
import json
import typing
import logging

LOG = logging.getLogger("swm")


class BaseConnector:
    def __init__(self, provider_name: str):
        self._provider_name = provider_name
        self._test_responses = self._get_test_responses()

    def find_image(self, image_id: str) -> typing.Union:
        images = self.list_images()
        found = [it for it in images if it.id == image_id]
        if found:
            return found[0]
        return None

    def _get_test_responses(self) -> typing.Dict[str, str]:
        file_path = os.getenv("SWM_TEST_CONFIG", None)
        if file_path:
            with open(file_path, "r") as responses_file:
                json_str = responses_file.read()
                try:
                    json_objects = json.loads(json_str)
                    for json_obj in json_objects:
                        if json_obj.get("provider", None) == self._provider_name:
                            return json_obj.get("requests", {})
                except json.decoder.JSONDecodeError as e:
                    LOG.error(e)
        return {}

    def _get_runtime_params(self, runtime: str) -> dict[str, str]:
        runtime_params: dict[str, str] = {}
        LOG.debug(f"Runtime parameters string: {runtime}")
        for it in runtime.split(","):
            [key, value] = it.split("=", 1)
            runtime_params[key.strip()] = value.strip()
        LOG.debug(f"Runtime parameters parsed: {runtime_params}")
        return runtime_params
