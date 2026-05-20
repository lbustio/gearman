from __future__ import annotations

from typing import Any

from .codec import decode_result, encode_payload


def submit_sync_job(client: Any, task: str, payload: dict[str, Any]) -> dict[str, Any]:
    job_request = client.submit_job(task, encode_payload(payload), wait_until_complete=True)
    if getattr(job_request, "state", "") == "FAILED":
        raise RuntimeError(f"El job {task} falló")
    return decode_result(getattr(job_request, "result", None))


def submit_background_job(client: Any, task: str, payload: dict[str, Any]) -> str:
    job_request = client.submit_job(task, encode_payload(payload), background=True, wait_until_complete=False)
    return getattr(job_request, "job", "<sin-handle>")
