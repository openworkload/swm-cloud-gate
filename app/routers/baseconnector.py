import json
import logging
import os
import typing

LOG = logging.getLogger("swm")


class BaseConnector:
    def __init__(self, provider_name: str):
        self._provider_name = provider_name
        self._test_responses = self._get_test_responses()

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
