import json
import pathlib
import sys
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gearman_demo.gearman.status_reporter import WorkerStatusReporter


class DummyResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class WorkerStatusReporterTestCase(unittest.TestCase):
    @patch("gearman_demo.gearman.status_reporter.urllib.request.urlopen")
    def test_reports_worker_state_to_api_over_http(self, urlopen) -> None:
        urlopen.return_value = DummyResponse()
        reporter = WorkerStatusReporter(
            api_url="http://127.0.0.1:8000",
            worker_id="cpu-06",
            pid=123,
            worker_index=5,
            worker_count=16,
            registered_tasks=("demo.analyze",),
        )

        reporter.mark_ready()
        reporter.mark_started(task="demo.analyze", job_id="job-1", gearman_handle="H:1")
        reporter.mark_finished(task="demo.analyze", duration_ms=12.345)

        self.assertEqual(urlopen.call_count, 3)
        last_request = urlopen.call_args.args[0]
        last_payload = json.loads(last_request.data.decode("utf-8"))
        self.assertEqual(last_request.full_url, "http://127.0.0.1:8000/api/worker-status")
        self.assertEqual(last_payload["worker_id"], "cpu-06")
        self.assertEqual(last_payload["status"], "ready")
        self.assertFalse(last_payload["busy"])
        self.assertEqual(last_payload["jobs_processed"], 1)
        self.assertEqual(last_payload["jobs_in_progress"], 0)
        self.assertEqual(last_payload["registered_tasks"], ["demo.analyze"])

    def test_network_errors_do_not_crash_worker(self) -> None:
        reporter = WorkerStatusReporter(
            api_url="http://127.0.0.1:1",
            worker_id="cpu-01",
            timeout=0.01,
        )

        payload = reporter.mark_ready()

        self.assertEqual(payload["worker_id"], "cpu-01")
        self.assertIsNotNone(reporter.last_error)


if __name__ == "__main__":
    unittest.main()
