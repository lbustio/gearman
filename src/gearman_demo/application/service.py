from __future__ import annotations

import uuid
from collections import deque
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from gearman_demo.domain.task_catalog import TASK_CATALOG
from gearman_demo.gearman.client import submit_background_job, submit_sync_job
from gearman_demo.gearman.compat import apply_gearman3_python312_patch
from gearman_demo.gearman.telemetry import read_events, to_jsonable


class GearmanServiceError(RuntimeError):
    """Error de comunicación con Gearman."""


class GearmanDemoService:
    """Servicio para ejecutar tareas Gearman y mantener historial local de jobs."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4730,
        history_limit: int = 200,
        client_factory: Any | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.server = f"{host}:{port}"
        self.history_limit = history_limit
        self._client_factory = client_factory
        self._history: deque[dict[str, Any]] = deque(maxlen=history_limit)
        self._events: deque[dict[str, Any]] = deque(maxlen=history_limit * 10)
        self._lock = Lock()

    def _new_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()

        apply_gearman3_python312_patch()
        import gearman

        return gearman.GearmanClient([self.server])

    def _save_history(self, record: dict[str, Any]) -> dict[str, Any]:
        record = to_jsonable(record)
        with self._lock:
            self._history.appendleft(record)
        return record

    def _now(self) -> str:
        return datetime.now(UTC).isoformat()

    def _log_event(
        self,
        *,
        local_job_id: str,
        task: str,
        stage: str,
        status: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "job_id": local_job_id,
            "created_at": self._now(),
            "source": "api",
            "worker_id": None,
            "pid": None,
            "task": task,
            "stage": stage,
            "status": status,
            "message": message,
            "gearman_handle": None,
            "duration_ms": None,
            "details": to_jsonable(details or {}),
        }
        with self._lock:
            self._events.appendleft(event)
        return event

    def list_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [to_jsonable(job) for job in self._history]

    def list_events(self, local_job_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            events = [to_jsonable(event) for event in self._events]
        events.extend(read_events(job_id=local_job_id, limit=limit))
        if local_job_id:
            events = [event for event in events if event["job_id"] == local_job_id]
        events.sort(key=lambda event: event.get("created_at", ""), reverse=True)
        return events[:limit]

    def get_job(self, local_job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = next((job for job in self._history if job["id"] == local_job_id), None)
        return to_jsonable(job) if job else None

    def report(self) -> dict[str, Any]:
        jobs = self.list_jobs()
        totals: dict[str, int] = {
            "analyze": 0,
            "shard": 0,
            "background_log": 0,
            "failed": 0,
        }
        for job in jobs:
            totals[job["kind"]] = totals.get(job["kind"], 0) + 1
            if job["status"] == "failed":
                totals["failed"] += 1
        return {
            "server": self.server,
            "total_jobs": len(jobs),
            "totals": totals,
            "last_job_at": jobs[0]["created_at"] if jobs else None,
            "tasks": list(TASK_CATALOG),
        }

    def run_analyze(self, text: str, top_n: int) -> dict[str, Any]:
        return self._run_sync(kind="analyze", task="demo.analyze", payload={"text": text, "top_n": top_n})

    def run_shard(self, text: str, shard_size: int) -> dict[str, Any]:
        return self._run_sync(
            kind="shard",
            task="demo.shard",
            payload={"text": text, "shard_size": shard_size},
        )

    def run_background_log(self, message: str) -> dict[str, Any]:
        local_job_id = str(uuid.uuid4())
        now = self._now()
        payload = {"message": message}
        self._log_event(
            local_job_id=local_job_id,
            task="demo.bg_log",
            stage="submit",
            status="running",
            message="Enviando job background a Gearman",
            details={"message_chars": len(message)},
        )

        try:
            gearman_handle = submit_background_job(
                self._new_client(),
                "demo.bg_log",
                {**payload, "_trace_job_id": local_job_id},
            )
            self._log_event(
                local_job_id=local_job_id,
                task="demo.bg_log",
                stage="submit",
                status="accepted",
                message="Gearman aceptó el job background",
                details={"gearman_handle": gearman_handle},
            )
            record = {
                "id": local_job_id,
                "created_at": now,
                "kind": "background_log",
                "task": "demo.bg_log",
                "status": "accepted",
                "payload": payload,
                "result": {"gearman_handle": gearman_handle},
            }
        except Exception as exc:  # pragma: no cover - depende de red/gearmand
            self._log_event(
                local_job_id=local_job_id,
                task="demo.bg_log",
                stage="submit",
                status="failed",
                message="Falló el envío del job background",
                details={"error": str(exc)},
            )
            record = {
                "id": local_job_id,
                "created_at": now,
                "kind": "background_log",
                "task": "demo.bg_log",
                "status": "failed",
                "payload": payload,
                "error": str(exc),
            }
            self._save_history(record)
            raise GearmanServiceError(str(exc)) from exc

        return self._save_history(record)

    def run_pipeline(self, text: str, shard_size: int, top_n: int) -> dict[str, Any]:
        local_job_id = str(uuid.uuid4())
        now = self._now()
        payload = {"text": text, "shard_size": shard_size, "top_n": top_n}
        client = self._new_client()
        self._log_event(
            local_job_id=local_job_id,
            task="demo.pipeline",
            stage="pipeline",
            status="running",
            message="Pipeline iniciado",
            details={"text_chars": len(text), "shard_size": shard_size, "top_n": top_n},
        )

        try:
            self._log_event(
                local_job_id=local_job_id,
                task="demo.shard",
                stage="shard",
                status="running",
                message="Ejecutando demo.shard",
                details={"shard_size": shard_size},
            )
            shard_result = submit_sync_job(
                client,
                "demo.shard",
                {"text": text, "shard_size": shard_size, "_trace_job_id": local_job_id},
            )
            shard_count = len(shard_result.get("shards", []))
            self._log_event(
                local_job_id=local_job_id,
                task="demo.shard",
                stage="shard",
                status="completed",
                message=f"demo.shard completó {shard_count} shards",
                details={"shard_count": shard_count},
            )
            shard_jobs = []
            totals = {
                "chars": 0,
                "tokens": 0,
                "unique_tokens_estimate": 0,
                "sentiment_score": 0,
            }

            for index, shard in enumerate(shard_result.get("shards", []), start=1):
                self._log_event(
                    local_job_id=local_job_id,
                    task="demo.analyze",
                    stage="analyze",
                    status="running",
                    message=f"Analizando shard {index}/{shard_count}",
                    details={"shard_index": index, "shard_count": shard_count, "chars": len(shard)},
                )
                analysis = submit_sync_job(
                    client,
                    "demo.analyze",
                    {
                        "text": shard,
                        "top_n": top_n,
                        "_trace_job_id": local_job_id,
                        "_trace_shard_index": index,
                        "_trace_shard_count": shard_count,
                    },
                )
                sentiment = analysis.get("sentiment", {})
                totals["chars"] += int(analysis.get("chars", 0))
                totals["tokens"] += int(analysis.get("tokens", 0))
                totals["unique_tokens_estimate"] += int(analysis.get("unique_tokens", 0))
                totals["sentiment_score"] += int(sentiment.get("score", 0))
                shard_jobs.append(
                    {
                        "index": index,
                        "chars": analysis.get("chars", 0),
                        "tokens": analysis.get("tokens", 0),
                        "sentiment": sentiment,
                        "top_tokens": analysis.get("top_tokens", []),
                    }
                )
                self._log_event(
                    local_job_id=local_job_id,
                    task="demo.analyze",
                    stage="analyze",
                    status="completed",
                    message=f"Shard {index}/{shard_count} analizado",
                    details={
                        "shard_index": index,
                        "tokens": analysis.get("tokens", 0),
                        "sentiment_score": sentiment.get("score", 0),
                    },
                )

            self._log_event(
                local_job_id=local_job_id,
                task="demo.pipeline",
                stage="aggregate",
                status="running",
                message="Agregando resultados del pipeline",
                details={"gearman_jobs": 1 + len(shard_jobs)},
            )

            record = {
                "id": local_job_id,
                "created_at": now,
                "kind": "pipeline",
                "task": "demo.pipeline",
                "status": "completed",
                "payload": payload,
                "result": {
                    "stages": ["demo.shard", "demo.analyze"],
                    "gearman_jobs": 1 + len(shard_jobs),
                    "shard_count": len(shard_jobs),
                    "totals": totals,
                    "shards": shard_jobs,
                },
            }
            self._log_event(
                local_job_id=local_job_id,
                task="demo.pipeline",
                stage="pipeline",
                status="completed",
                message="Pipeline completado",
                details={"gearman_jobs": 1 + len(shard_jobs), "tokens": totals["tokens"]},
            )
        except Exception as exc:  # pragma: no cover - depende de red/gearmand
            self._log_event(
                local_job_id=local_job_id,
                task="demo.pipeline",
                stage="pipeline",
                status="failed",
                message="Pipeline falló",
                details={"error": str(exc)},
            )
            record = {
                "id": local_job_id,
                "created_at": now,
                "kind": "pipeline",
                "task": "demo.pipeline",
                "status": "failed",
                "payload": payload,
                "error": str(exc),
            }
            self._save_history(record)
            raise GearmanServiceError(str(exc)) from exc

        return self._save_history(record)

    def _run_sync(self, *, kind: str, task: str, payload: dict[str, Any]) -> dict[str, Any]:
        local_job_id = str(uuid.uuid4())
        now = self._now()
        self._log_event(
            local_job_id=local_job_id,
            task=task,
            stage="submit",
            status="running",
            message=f"Ejecutando {task}",
            details={"kind": kind},
        )

        try:
            result = submit_sync_job(self._new_client(), task, {**payload, "_trace_job_id": local_job_id})
            self._log_event(
                local_job_id=local_job_id,
                task=task,
                stage="submit",
                status="completed",
                message=f"{task} completó correctamente",
                details={"result_keys": sorted(result.keys())},
            )
            record = {
                "id": local_job_id,
                "created_at": now,
                "kind": kind,
                "task": task,
                "status": "completed",
                "payload": payload,
                "result": result,
            }
        except Exception as exc:  # pragma: no cover - depende de red/gearmand
            self._log_event(
                local_job_id=local_job_id,
                task=task,
                stage="submit",
                status="failed",
                message=f"{task} falló",
                details={"error": str(exc)},
            )
            record = {
                "id": local_job_id,
                "created_at": now,
                "kind": kind,
                "task": task,
                "status": "failed",
                "payload": payload,
                "error": str(exc),
            }
            self._save_history(record)
            raise GearmanServiceError(str(exc)) from exc

        return self._save_history(record)
