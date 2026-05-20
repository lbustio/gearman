import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gearman_demo.application.service import GearmanDemoService, GearmanServiceError


class GearmanDemoServiceTestCase(unittest.TestCase):
    @patch("gearman_demo.application.service.submit_sync_job")
    def test_run_analyze_success(self, submit_sync_job) -> None:
        submit_sync_job.return_value = {"tokens": 2}
        service = GearmanDemoService(client_factory=lambda: object())

        record = service.run_analyze("hola mundo", top_n=5)

        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["kind"], "analyze")
        self.assertEqual(record["result"]["tokens"], 2)
        self.assertEqual(len(service.list_jobs()), 1)

    @patch("gearman_demo.application.service.submit_sync_job")
    def test_run_shard_failure(self, submit_sync_job) -> None:
        submit_sync_job.side_effect = RuntimeError("gearman down")
        service = GearmanDemoService(client_factory=lambda: object())

        with self.assertRaises(GearmanServiceError):
            service.run_shard("texto", shard_size=10)

        jobs = service.list_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["status"], "failed")

    @patch("gearman_demo.application.service.submit_background_job")
    def test_background_log_success(self, submit_background_job) -> None:
        submit_background_job.return_value = "H:127.0.0.1:1"
        service = GearmanDemoService(client_factory=lambda: object())

        record = service.run_background_log("hola")

        self.assertEqual(record["status"], "accepted")
        self.assertIn("gearman_handle", record["result"])

    @patch("gearman_demo.application.service.submit_background_job")
    def test_background_log_serializes_unknown_handle(self, submit_background_job) -> None:
        submit_background_job.return_value = SimpleNamespace(job="H:127.0.0.1:1")
        service = GearmanDemoService(client_factory=lambda: object())

        record = service.run_background_log("hola")

        self.assertIsInstance(record["result"]["gearman_handle"], str)

    @patch("gearman_demo.application.service.submit_sync_job")
    def test_report_summary(self, submit_sync_job) -> None:
        submit_sync_job.side_effect = [{"ok": True}, RuntimeError("error")]
        service = GearmanDemoService(client_factory=lambda: object())

        service.run_analyze("hola", top_n=5)
        with self.assertRaises(GearmanServiceError):
            service.run_analyze("hola", top_n=5)

        report = service.report()
        self.assertEqual(report["total_jobs"], 2)
        self.assertEqual(report["totals"]["analyze"], 2)
        self.assertEqual(report["totals"]["failed"], 1)
        self.assertGreaterEqual(len(report["tasks"]), 3)

    @patch("gearman_demo.application.service.submit_sync_job")
    def test_pipeline_success(self, submit_sync_job) -> None:
        submit_sync_job.side_effect = [
            {"shards": ["excelente texto", "bug lento"]},
            {"chars": 15, "tokens": 2, "unique_tokens": 2, "sentiment": {"score": 1}, "top_tokens": []},
            {"chars": 9, "tokens": 2, "unique_tokens": 2, "sentiment": {"score": -2}, "top_tokens": []},
        ]
        service = GearmanDemoService(client_factory=lambda: object())

        record = service.run_pipeline("excelente texto bug lento", shard_size=16, top_n=5)

        self.assertEqual(record["status"], "completed")
        self.assertEqual(record["kind"], "pipeline")
        self.assertEqual(record["result"]["gearman_jobs"], 3)
        self.assertEqual(record["result"]["totals"]["sentiment_score"], -1)
        events = service.list_events(local_job_id=record["id"])
        messages = [event["message"] for event in events]
        self.assertIn("Pipeline completado", messages)
        self.assertTrue(any("Analizando shard" in message for message in messages))

    @patch("gearman_demo.application.service.submit_sync_job")
    def test_events_are_recorded_for_sync_job(self, submit_sync_job) -> None:
        submit_sync_job.return_value = {"tokens": 2}
        service = GearmanDemoService(client_factory=lambda: object())

        record = service.run_analyze("hola mundo", top_n=5)
        events = service.list_events(local_job_id=record["id"])

        self.assertEqual(events[0]["status"], "completed")
        self.assertEqual(events[-1]["status"], "running")


if __name__ == "__main__":
    unittest.main()
