import atexit
import pickle  # nosec B403
import logging
from pathlib import Path
from datetime import datetime, timedelta
from functools import lru_cache

from pydantic import BaseModel

from swmcloudgate import config

LOG = logging.getLogger("swm")


class Cache:
    """Class for caching rarely changed data retrieved from cloud provider.
    The cache is maintained in memory but saved in file on exit and then loaded on start.
    """

    _cache_file_path: Path = Path()
    _data: list[tuple[datetime, list[str], list[BaseModel]]] = []

    def __init__(self, data_kind: str, data_provider: str, settings: config.Settings) -> None:
        self._data_kind = data_kind
        self._data_provider = data_provider
        self._settings = settings
        self._data, self._cache_file_path = self._load_from_filesystem()
        LOG.debug(f"Start {data_kind} cache: {self._cache_file_path}")

    def __del__(self) -> None:
        LOG.debug(f"Stop {self._data_kind} cache")
        if self._data:
            self._write(self._cache_file_path, self._data)

    @property
    def expire(self) -> int:
        return self._settings.cache_expire

    def fetch_and_update(self, key: list[str]) -> list[BaseModel] | None:
        LOG.debug(f"Try to fetch {self._data_kind} from in-memory cache by key: {key}")
        for timestamp, cached_key, cached_value in self._data[:]:
            if timestamp >= datetime.now() - timedelta(seconds=self._settings.cache_expire):
                if key == cached_key:
                    return cached_value
        return None

    def update(self, key: list[str], value: list[BaseModel]) -> tuple[int, int]:
        LOG.debug(f"Update in-memory cache: {self._data_kind}")
        changed: int = 0
        deleted: int = 0

        data: list[tuple[datetime, list[str], list[BaseModel]]] = []
        found = False
        now = datetime.now()
        fresh_timestamp = now - timedelta(seconds=self._settings.cache_expire)
        for timestamp, cached_key, cached_value in self._data:
            if cached_key == key:
                if timestamp < fresh_timestamp:
                    deleted += 1
                    continue
                found = True
                if cached_value != value:
                    data.append((now, cached_key, value))
                    changed += 1
                else:
                    data.append((timestamp, cached_key, cached_value))
            elif timestamp < fresh_timestamp:
                deleted += 1
            else:
                data.append((timestamp, cached_key, cached_value))  # not changed
        self._data = data

        if not found:
            self._data.append((now, key, value))
            changed += 1

        return changed, deleted

    def _load_from_filesystem(self) -> tuple[list[tuple[datetime, list[str], list[BaseModel]]], Path]:
        LOG.debug(f"Load cache data from directory: {self._settings.cache_dir}")
        data: list[tuple[datetime, list[str], list[BaseModel]]] = []
        cache_file_path = Path(f"{self._settings.cache_dir}/cloud-gate-{self._data_provider}-{self._data_kind}.dat")
        if cache_file_path.exists():
            data = self._read(cache_file_path)
        else:
            cache_file_path.parent.mkdir(parents=True, exist_ok=True)
            cache_file_path.touch(exist_ok=True)
        return data, cache_file_path

    def _read(self, file_path: Path) -> list[tuple[datetime, list[str], list[BaseModel]]]:
        LOG.debug(f"Read cache: {file_path}")
        try:
            with open(file_path, "rb") as file:
                return pickle.load(file)  # nosec B301
        except EOFError as e:
            LOG.debug(f"Cannot load cache file {file_path}: {e}")
        except FileNotFoundError as e:
            LOG.debug(f"File not found: {e}")
        return []

    def _write(self, file_path: Path, data: list[tuple[datetime, list[str], list[BaseModel]]]) -> None:
        with open(file_path, "wb") as file:
            pickle.dump(data, file)  # nosec B301


@lru_cache(maxsize=64)
def data_cache(data_kind: str, data_provider: str, cache_dir: str = "") -> Cache:
    settings = config.get_settings(cache_dir) if cache_dir else config.get_settings()
    return Cache(data_kind, data_provider, settings)


def cleanup():
    data_cache.cache_clear()


atexit.register(cleanup)
