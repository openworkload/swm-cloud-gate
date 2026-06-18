import os
from pathlib import Path
from functools import lru_cache

import yaml
from pydantic import Field, BaseModel

DEFAULT_CONFIG_PATH = Path(os.path.expanduser("~/.swm/cloud-gate.yaml"))


class BaseSection(BaseModel):
    cache_expire: int = 7200000
    cache_dir: Path = Field(..., description="Cache directory path (supports ~)")


class AzureApiCredentials(BaseModel):
    subscription_id: str = ""  # allow empty; can enforce non-empty in prod
    tenant_id: str = ""
    app_id: str = ""


class AzureContainerRegistry(BaseModel):
    user: str = ""
    password: str = ""


class AzureStorage(BaseModel):
    account: str = ""
    key: str = ""
    container: str = ""


class AzureVmImage(BaseModel):
    publisher: str = ""
    offer: str = ""
    skus: str = ""


class AzureProvider(BaseModel):
    api_credentials: AzureApiCredentials = AzureApiCredentials()
    container_registry: AzureContainerRegistry = AzureContainerRegistry()
    storage: AzureStorage = AzureStorage()
    vm_image: AzureVmImage = AzureVmImage()
    user_ssh_cert: str = ""


class Providers(BaseModel):
    azure: AzureProvider = AzureProvider()


class Settings(BaseModel):
    version: int = 1
    base: BaseSection = BaseSection(cache_dir=Path("~/.swm/cache"))
    providers: Providers = Providers()


def load_config(path: str | Path) -> Settings:
    path = Path(path).expanduser()
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Settings.parse_obj(data)


# Env var override: lets tests (and one-off invocations) point at a different
# cloud-gate.yaml without threading the path through every caller. Matches the
# existing SWM_TEST_CONFIG pattern used by BaseConnector for test responses.
CONFIG_ENV_VAR = "SWM_GATE_CONFIG"


@lru_cache()
def get_settings(config_file: Path | None = None) -> Settings:
    if config_file is None:
        env_path = os.environ.get(CONFIG_ENV_VAR)
        config_file = Path(env_path).expanduser() if env_path else DEFAULT_CONFIG_PATH
    return load_config(config_file)
