from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


EVENT_LOG_ENV = "GEARMAN_DEMO_EVENT_LOG"
WORKER_LOG_DIR_ENV = "GEARMAN_DEMO_WORKER_LOG_DIR"


def event_log_path() -> Path:
    configured = os.environ.get(EVENT_LOG_ENV)
    if configured:
        return Path(configured)
    return Path.cwd() / ".runtime" / "events.jsonl"


def worker_log_dir() -> Path:
    configured = os.environ.get(WORKER_LOG_DIR_ENV)
    if configured:
        return Path(configured)
    return Path.cwd() / ".runtime" / "workers"


def reset_event_log(path: Path | None = None) -> None:
    log_path = path or event_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("", encoding="utf-8")


def to_jsonable(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_jsonable(item) for item in value]
    return repr(value)


def append_event(
    *,
    task: str,
    stage: str,
    status: str,
    message: str,
    job_id: str | None = None,
    worker_id: str | None = None,
    gearman_handle: str | None = None,
    duration_ms: float | None = None,
    details: dict[str, Any] | None = None,
    source: str = "worker",
) -> dict[str, Any]:
    event = {
        "id": str(uuid.uuid4()),
        "job_id": to_jsonable(job_id),
        "created_at": datetime.now(UTC).isoformat(),
        "source": source,
        "worker_id": to_jsonable(worker_id),
        "pid": os.getpid(),
        "task": to_jsonable(task),
        "stage": to_jsonable(stage),
        "status": to_jsonable(status),
        "message": to_jsonable(message),
        "gearman_handle": to_jsonable(gearman_handle),
        "duration_ms": round(duration_ms, 2) if duration_ms is not None else None,
        "details": to_jsonable(details or {}),
    }
    log_path = event_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def read_events(
    *,
    job_id: str | None = None,
    limit: int = 200,
    path: Path | None = None,
) -> list[dict[str, Any]]:
    log_path = path or event_log_path()
    if not log_path.exists():
        return []

    events: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if job_id and event.get("job_id") != job_id:
            continue
        events.append(event)

    events.sort(key=lambda event: event.get("created_at", ""), reverse=True)
    return events[:limit]
