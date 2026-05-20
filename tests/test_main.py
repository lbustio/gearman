import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from main import cpu_worker_id


class MainTestCase(unittest.TestCase):
    def test_cpu_worker_id_is_zero_padded(self) -> None:
        self.assertEqual(cpu_worker_id(0), "cpu-01")
        self.assertEqual(cpu_worker_id(5), "cpu-06")
        self.assertEqual(cpu_worker_id(63), "cpu-64")


if __name__ == "__main__":
    unittest.main()
