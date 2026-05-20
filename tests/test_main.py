import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import cpu_worker_id, local_api_url


class MainTestCase(unittest.TestCase):
    def test_cpu_worker_id_is_zero_padded(self) -> None:
        self.assertEqual(cpu_worker_id(0), "cpu-01")
        self.assertEqual(cpu_worker_id(5), "cpu-06")
        self.assertEqual(cpu_worker_id(63), "cpu-64")

    def test_local_api_url_uses_loopback_for_wildcard_hosts(self) -> None:
        self.assertEqual(local_api_url("0.0.0.0", 8000), "http://127.0.0.1:8000")
        self.assertEqual(local_api_url("::", 8001), "http://127.0.0.1:8001")
        self.assertEqual(local_api_url("localhost", 8002), "http://localhost:8002")


if __name__ == "__main__":
    unittest.main()
