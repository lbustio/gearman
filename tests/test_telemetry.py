import os
import pathlib
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gearman_demo.gearman.telemetry import (
    EVENT_LOG_ENV,
    WORKER_LOG_DIR_ENV,
    append_event,
    read_events,
    reset_event_log,
    to_jsonable,
)
from gearman_demo.gearman.worker import configure_worker_logger, log_worker_action, summarize_worker_result


class TelemetryTestCase(unittest.TestCase):
    def test_append_and_read_events(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous = os.environ.get(EVENT_LOG_ENV)
            os.environ[EVENT_LOG_ENV] = str(pathlib.Path(temp_dir) / "events.jsonl")
            try:
                reset_event_log()
                append_event(
                    job_id="job-1",
                    task="demo.analyze",
                    stage="worker.process",
                    status="completed",
                    message="done",
                    worker_id="cpu-1",
                    duration_ms=12.345,
                )

                events = read_events(job_id="job-1")

                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]["worker_id"], "cpu-1")
                self.assertEqual(events[0]["duration_ms"], 12.35)
            finally:
                if previous is None:
                    os.environ.pop(EVENT_LOG_ENV, None)
                else:
                    os.environ[EVENT_LOG_ENV] = previous

    def test_summarize_worker_result_for_analyze(self) -> None:
        summary = summarize_worker_result(
            "demo.analyze",
            {
                "chars": 10,
                "tokens": 2,
                "unique_tokens": 2,
                "top_tokens": [["hola", 1], ["mundo", 1]],
                "sentiment": {"score": 1},
            },
        )

        self.assertEqual(summary["tokens"], 2)
        self.assertEqual(summary["sentiment_score"], 1)

    def test_to_jsonable_converts_unknown_objects(self) -> None:
        class Unknown:
            pass

        value = to_jsonable({"obj": Unknown(), "items": [b"ok"]})

        self.assertIn("Unknown", value["obj"])
        self.assertEqual(value["items"], ["ok"])

    def test_worker_logger_writes_independent_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            previous = os.environ.get(WORKER_LOG_DIR_ENV)
            os.environ[WORKER_LOG_DIR_ENV] = temp_dir
            try:
                logger = configure_worker_logger("cpu-06")
                log_worker_action(logger, "JOB_COMPLETED", task="demo.analyze", duration_ms=1.25)

                content = pathlib.Path(temp_dir, "cpu-06.log").read_text(encoding="utf-8")

                self.assertIn("LOG_FILE", content)
                self.assertIn("JOB_COMPLETED", content)
                self.assertIn("demo.analyze", content)
            finally:
                if previous is None:
                    os.environ.pop(WORKER_LOG_DIR_ENV, None)
                else:
                    os.environ[WORKER_LOG_DIR_ENV] = previous


if __name__ == "__main__":
    unittest.main()
