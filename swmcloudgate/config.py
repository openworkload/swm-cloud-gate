import os
import json
from pathlib import Path
from functools import lru_cache

from pydantic import Field, BaseModel, ConfigDict, BaseSettings


class AzureStorage(BaseModel):
    account: str
    token: str


class AzureSettings(BaseModel):
    storage: AzureStorage


class OpenStackSettings(BaseModel):
    pass


class BaseConfig(BaseModel):
    cache_expire: int = Field(14 * 24 * 3600)
    cache_dir: str = Field(os.path.expanduser("~/.cache/swm"))


class Settings(BaseSettings):
    base: BaseConfig
    azure: AzureSettings | None = None
    openstack: OpenStackSettings | None = None


@lru_cache()
def get_settings(config_file: Path) -> Settings:
    with open(config_file, "r") as file:
        config_data = json.load(file)
    return Settings(**config_data)
