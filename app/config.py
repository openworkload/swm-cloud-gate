import os
from functools import lru_cache

from pydantic import BaseSettings

SWM_USER_DIR = f'{os.path.expanduser("~")}/.swm'


class Settings(BaseSettings):
    cache_expire: int = 3600
    cache_file: str = f"{SWM_USER_DIR}/cloud-gate.cache"

    class Config:
        env_file = f"{SWM_USER_DIR}/cloud-gate.conf"


@lru_cache()
def get_settings():
    return Settings()
