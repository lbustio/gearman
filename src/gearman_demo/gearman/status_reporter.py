from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from .telemetry import to_jsonable


class WorkerStatusReporter:
    """Mantiene y reporta por HTTP el estado operativo de un worker."""

    def __init__(
        self,
        *,
        api_url: str | None,
        worker_id: str,
        pid: int | None = None,
        worker_index: int = 0,
        worker_count: int = 1,
        registered_tasks: list[str] | tuple[str, ...] = (),
        timeout: float = 0.5,
    ) -> None:
        self.api_url = api_url.rstrip("/") if api_url else None
        self.worker_id = worker_id
        self.pid = pid if pid is not None else os.getpid()
        self.worker_index = worker_index
        self.worker_count = worker_count
        self.registered_tasks = list(registered_tasks)
        self.timeout = timeout

        self.status = "booting"
        self.busy = False
        self.jobs_in_progress = 0
        self.jobs_processed = 0
        self.jobs_failed = 0
        self.current_task: str | None = None
        self.current_job_id: str | None = None
        self.current_gearman_handle: str | None = None
        self.last_job_type: str | None = None
        self.last_job_started_at: str | None = None
        self.last_job_finished_at: str | None = None
        self.last_duration_ms: float | None = None
        self.updated_at = self._now()
        self.last_error: str | None = None

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def payload(self, details: dict[str, Any] | None = None) -> dict[str, Any]:
        report_details = dict(details or {})
        if self.last_error:
            report_details["report_error"] = self.last_error
        return to_jsonable(
            {
                "worker_id": self.worker_id,
                "pid": self.pid,
                "worker_index": self.worker_index,
                "worker_count": self.worker_count,
                "status": self.status,
                "busy": self.busy,
                "jobs_in_progress": self.jobs_in_progress,
                "jobs_processed": self.jobs_processed,
                "jobs_failed": self.jobs_failed,
                "current_task": self.current_task,
                "current_job_id": self.current_job_id,
                "current_gearman_handle": self.current_gearman_handle,
                "last_job_type": self.last_job_type,
                "last_job_started_at": self.last_job_started_at,
                "last_job_finished_at": self.last_job_finished_at,
                "last_duration_ms": self.last_duration_ms,
                "registered_tasks": self.registered_tasks,
                "updated_at": self.updated_at,
                "details": report_details,
            }
        )

    def report(self, details: dict[str, Any] | None = None) -> dict[str, Any]:
        self.updated_at = self._now()
        payload = self.payload(details=details)
        if not self.api_url:
            return payload

        request = urllib.request.Request(
            f"{self.api_url}/api/worker-status",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout):
                self.last_error = None
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            self.last_error = str(exc)
        return payload

    def mark_ready(self, details: dict[str, Any] | None = None) -> dict[str, Any]:
        self.status = "ready"
        self.busy = False
        self.jobs_in_progress = 0
        self.current_task = None
        self.current_job_id = None
        self.current_gearman_handle = None
        return self.report(details=details)

    def mark_started(
        self,
        *,
        task: str,
        job_id: str,
        gearman_handle: str | None,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.status = "busy"
        self.busy = True
        self.jobs_in_progress += 1
        self.current_task = task
        self.current_job_id = job_id
        self.current_gearman_handle = gearman_handle
        self.last_job_type = task
        self.last_job_started_at = self._now()
        self.last_job_finished_at = None
        self.last_duration_ms = None
        return self.report(details=details)

    def mark_finished(
        self,
        *,
        task: str,
        duration_ms: float,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.jobs_in_progress = max(0, self.jobs_in_progress - 1)
        self.jobs_processed += 1
        self.status = "ready" if self.jobs_in_progress == 0 else "busy"
        self.busy = self.jobs_in_progress > 0
        self.current_task = None if not self.busy else self.current_task
        self.current_job_id = None if not self.busy else self.current_job_id
        self.current_gearman_handle = None if not self.busy else self.current_gearman_handle
        self.last_job_type = task
        self.last_job_finished_at = self._now()
        self.last_duration_ms = round(duration_ms, 2)
        return self.report(details=details)

    def mark_failed(
        self,
        *,
        task: str,
        duration_ms: float,
        error: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.jobs_in_progress = max(0, self.jobs_in_progress - 1)
        self.jobs_failed += 1
        self.status = "failed" if self.jobs_in_progress == 0 else "busy"
        self.busy = self.jobs_in_progress > 0
        self.current_task = None if not self.busy else self.current_task
        self.current_job_id = None if not self.busy else self.current_job_id
        self.current_gearman_handle = None if not self.busy else self.current_gearman_handle
        self.last_job_type = task
        self.last_job_finished_at = self._now()
        self.last_duration_ms = round(duration_ms, 2)
        return self.report(details={**(details or {}), "error": error})

    def mark_stopped(self, details: dict[str, Any] | None = None) -> dict[str, Any]:
        self.status = "stopped"
        self.busy = False
        self.jobs_in_progress = 0
        self.current_task = None
        self.current_job_id = None
        self.current_gearman_handle = None
        return self.report(details=details)


def monotonic_duration_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000
