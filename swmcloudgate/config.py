import os
from functools import lru_cache

from pydantic import BaseSettings

USER_DIR = os.path.expanduser("~")


class Settings(BaseSettings):
    cache_expire: int = 3600
    cache_dir: str

    class Config:
        env_file = f"{USER_DIR}/.swm/cloud-gate.conf"


@lru_cache()
def get_settings(cache_dir: str = f"{USER_DIR}/.cache/swm") -> Settings:
    return Settings(cache_dir=cache_dir)
