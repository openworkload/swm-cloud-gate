import pickle
import unittest
from pathlib import Path
from datetime import datetime, timedelta
from tempfile import TemporaryDirectory

from swmcloudgate import cache
from swmcloudgate.routers.models import BaseModel


class TestCache(unittest.TestCase):
    def setUp(self):
        self._cache_dir = Path(TemporaryDirectory().name)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache = cache.data_cache("test_data_kind", "test", str(self._cache_dir))

    def test_fetch_and_update(self):
        self.assertIsNone(self._cache.fetch_and_update(["key1", "key2"]))

        outdated_timestamp = datetime.now() - timedelta(seconds=self._cache.expire + 1)
        self._cache._data.append((outdated_timestamp, ["key1", "key2"], [BaseModel()]))
        self.assertIsNone(self._cache.fetch_and_update(["key1", "key2"]))

        self._cache._data.append((datetime.now(), ["key1", "key2"], [BaseModel()]))
        self.assertEqual(self._cache.fetch_and_update(["key1", "key2"]), [BaseModel()])

    def test_update(self):
        changed, deleted = self._cache.update(["key1", "key2"], [BaseModel()])
        self.assertEqual(changed, 1)
        self.assertEqual(deleted, 0)
        self.assertEqual(len(self._cache._data), 1)

        changed, deleted = self._cache.update(["key1", "key2"], [BaseModel()])
        self.assertEqual(changed, 0)
        self.assertEqual(deleted, 0)
        self.assertEqual(len(self._cache._data), 1)

        outdated_timestamp = datetime.now() - timedelta(seconds=self._cache.expire + 1)
        self._cache._data.append((outdated_timestamp, ["key3", "key4"], [BaseModel()]))
        changed, deleted = self._cache.update(["key3", "key4"], [BaseModel()])
        self.assertEqual(changed, 1)
        self.assertEqual(deleted, 1)
        self.assertEqual(len(self._cache._data), 2)

    def test_load_from_filesystem(self):
        data, cache_file_path = self._cache._load_from_filesystem()
        self.assertEqual(data, [])
        self.assertEqual(cache_file_path, Path(f"{self._cache_dir}/cloud-gate-test-test_data_kind.dat"))

        cache_file_path = Path(f"{self._cache_dir}/cloud-gate-test-test_data_kind.dat")
        now = datetime.now()
        with open(cache_file_path, "wb") as file:
            pickle.dump([(now, ["key1", "key2"], [BaseModel()])], file)
        data, cache_file_path = self._cache._load_from_filesystem()
        self.assertEqual(data, [(now, ["key1", "key2"], [BaseModel()])])
        self.assertEqual(cache_file_path, Path(f"{self._cache_dir}/cloud-gate-test-test_data_kind.dat"))

    def test_read(self):
        cache_file_path = Path(f"{self._cache_dir}/non_existent_file.dat")
        data = self._cache._read(cache_file_path)
        self.assertEqual(data, [])

        now = datetime.now()
        cache_file_path = Path(f"{self._cache_dir}/cloud-gate-test-test_data_kind.dat")
        with open(cache_file_path, "wb") as file:
            pickle.dump([(now, ["key1", "key2"], [BaseModel()])], file)
        data = self._cache._read(cache_file_path)
        self.assertEqual(data, [(now, ["key1", "key2"], [BaseModel()])])

    def test_write(self):
        now = datetime.now()
        cache_file_path = Path(f"{self._cache_dir}/cloud-gate-test-test_data_kind.dat")
        self._cache._write(cache_file_path, [(now, ["key1", "key2"], [BaseModel()])])
        with open(cache_file_path, "rb") as file:
            data = pickle.load(file)
        self.assertEqual(data, [(now, ["key1", "key2"], [BaseModel()])])


if __name__ == "__main__":
    unittest.main()
