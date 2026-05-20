from __future__ import annotations

import argparse
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from gearman_demo.domain.task_catalog import TASK_CATALOG
from gearman_demo.domain.text_tasks import analyze_text, shard_text

from .codec import decode_payload, encode_payload
from .compat import apply_gearman3_python312_patch, gearman3_patch_status
from .status_reporter import WorkerStatusReporter, monotonic_duration_ms
from .telemetry import append_event, to_jsonable, worker_log_dir
from .worker_assignment import task_names_for_worker

LOGGER = logging.getLogger("gearman_demo.worker")


def configure_worker_logger(worker_id: str) -> logging.Logger:
    log_dir = worker_log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"{worker_id}.log"
    logger = logging.getLogger(f"gearman_demo.worker.{worker_id}")
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)
    logger.info("LOG_FILE path=%s worker_id=%s pid=%s", log_path, worker_id, os.getpid())
    return logger


def log_worker_action(logger: logging.Logger, action: str, **fields: Any) -> None:
    safe_fields = to_jsonable(fields)
    logger.info("%s %s", action, json.dumps(safe_fields, ensure_ascii=False, sort_keys=True))


def analyze_job(gearman_worker: Any, gearman_job: Any) -> bytes:
    payload = decode_payload(gearman_job.data)
    text = payload.get("text", "")
    top_n = int(payload.get("top_n", 5))
    result = analyze_text(text, top_n=top_n)
    result["task"] = "demo.analyze"
    return encode_payload(result)


def shard_job(gearman_worker: Any, gearman_job: Any) -> bytes:
    payload = decode_payload(gearman_job.data)
    text = payload.get("text", "")
    shard_size = int(payload.get("shard_size", 120))
    shards = shard_text(text, shard_size=shard_size)
    return encode_payload(
        {
            "task": "demo.shard",
            "shard_size": shard_size,
            "count": len(shards),
            "shards": shards,
        }
    )


def background_log_job(gearman_worker: Any, gearman_job: Any) -> bytes:
    payload = decode_payload(gearman_job.data)
    message = payload.get("message", "")
    LOGGER.info("[BG_JOB] %s", message)
    return encode_payload({"task": "demo.bg_log", "accepted": True})


def job_handle(gearman_job: Any) -> str | None:
    for attr_name in ("handle", "job_handle", "job"):
        value = getattr(gearman_job, attr_name, None)
        if value:
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return str(value)
    return None


def summarize_worker_result(task_name: str, result: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {"task": task_name}
    if task_name == "demo.shard":
        shards = result.get("shards", [])
        summary.update(
            {
                "shard_count": result.get("count", len(shards)),
                "shard_size": result.get("shard_size"),
                "sample": shards[:3],
            }
        )
    elif task_name == "demo.analyze":
        sentiment = result.get("sentiment", {})
        summary.update(
            {
                "chars": result.get("chars"),
                "tokens": result.get("tokens"),
                "unique_tokens": result.get("unique_tokens"),
                "top_tokens": result.get("top_tokens", [])[:5],
                "sentiment_score": sentiment.get("score"),
            }
        )
    elif task_name == "demo.bg_log":
        summary.update({"accepted": result.get("accepted", False)})
    else:
        summary.update({key: value for key, value in result.items() if key != "task"})
    return summary


def instrument_handler(
    task_name: str,
    handler: Any,
    worker_id: str,
    worker_logger: logging.Logger,
    status_reporter: WorkerStatusReporter,
) -> Any:
    def wrapped_handler(gearman_worker: Any, gearman_job: Any) -> bytes:
        started_at = time.perf_counter()
        payload = decode_payload(gearman_job.data)
        trace_job_id = payload.get("_trace_job_id") or str(uuid.uuid4())
        handle = job_handle(gearman_job)
        base_details = {
            "payload_keys": sorted(payload.keys()),
            "payload_bytes": len(gearman_job.data or b""),
        }
        if "_trace_shard_index" in payload:
            base_details["shard_index"] = payload.get("_trace_shard_index")
            base_details["shard_count"] = payload.get("_trace_shard_count")

        log_worker_action(
            worker_logger,
            "JOB_RECEIVED",
            job_id=trace_job_id,
            task=task_name,
            gearman_handle=handle,
            details=base_details,
        )
        status_reporter.mark_started(
            task=task_name,
            job_id=trace_job_id,
            gearman_handle=handle,
            details=base_details,
        )

        append_event(
            job_id=trace_job_id,
            task=task_name,
            stage="worker.receive",
            status="received",
            message=f"{worker_id} recibió {task_name}",
            worker_id=worker_id,
            gearman_handle=handle,
            details=base_details,
        )
        append_event(
            job_id=trace_job_id,
            task=task_name,
            stage="worker.process",
            status="running",
            message=f"{worker_id} está ejecutando {task_name}",
            worker_id=worker_id,
            gearman_handle=handle,
            details=base_details,
        )
        log_worker_action(
            worker_logger,
            "JOB_STARTED",
            job_id=trace_job_id,
            task=task_name,
            gearman_handle=handle,
            details=base_details,
        )

        try:
            result = handler(gearman_worker, gearman_job)
        except Exception as exc:
            duration_ms = monotonic_duration_ms(started_at)
            status_reporter.mark_failed(
                task=task_name,
                duration_ms=duration_ms,
                error=str(exc),
                details=base_details,
            )
            log_worker_action(
                worker_logger,
                "JOB_FAILED",
                job_id=trace_job_id,
                task=task_name,
                gearman_handle=handle,
                duration_ms=round(duration_ms, 2),
                error=str(exc),
                details=base_details,
            )
            append_event(
                job_id=trace_job_id,
                task=task_name,
                stage="worker.process",
                status="failed",
                message=f"{worker_id} falló ejecutando {task_name}",
                worker_id=worker_id,
                gearman_handle=handle,
                duration_ms=duration_ms,
                details={**base_details, "error": str(exc)},
            )
            raise

        duration_ms = monotonic_duration_ms(started_at)
        result_details: dict[str, Any] = {"result_bytes": len(result or b"")}
        try:
            decoded_result = decode_payload(result)
            result_details["result_keys"] = sorted(decoded_result.keys())
            result_details["result_summary"] = summarize_worker_result(task_name, decoded_result)
            if "count" in decoded_result:
                result_details["shard_count"] = decoded_result["count"]
            if "tokens" in decoded_result:
                result_details["tokens"] = decoded_result["tokens"]
        except Exception:
            pass

        log_worker_action(
            worker_logger,
            "JOB_COMPLETED",
            job_id=trace_job_id,
            task=task_name,
            gearman_handle=handle,
            duration_ms=round(duration_ms, 2),
            details={**base_details, **result_details},
        )
        status_reporter.mark_finished(
            task=task_name,
            duration_ms=duration_ms,
            details={**base_details, **result_details},
        )

        append_event(
            job_id=trace_job_id,
            task=task_name,
            stage="worker.process",
            status="completed",
            message=f"{worker_id} terminó {task_name}",
            worker_id=worker_id,
            gearman_handle=handle,
            duration_ms=duration_ms,
            details={**base_details, **result_details},
        )
        return result

    return wrapped_handler


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Worker Gearman para Demo")
    parser.add_argument("--host", default="127.0.0.1", help="Host del job server Gearman")
    parser.add_argument("--port", type=int, default=4730, help="Puerto del job server Gearman")
    parser.add_argument("--worker-index", type=int, default=0, help="Índice del worker dentro del pool")
    parser.add_argument("--worker-count", type=int, default=1, help="Cantidad total de workers en el pool")
    parser.add_argument("--worker-id", default=None, help="Identificador legible del worker")
    parser.add_argument(
        "--api-url",
        default=os.environ.get("GEARMAN_DEMO_API_URL"),
        help="URL base de la API para reportar estado del worker",
    )
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = build_parser().parse_args()
    apply_gearman3_python312_patch()
    patch_status = gearman3_patch_status()
    LOGGER.info("Compat gearman3 activa: %s", patch_status)
    if not patch_status["task_bytes"]:
        raise RuntimeError("El parche de compatibilidad task bytes/str de gearman3 no está activo")

    import gearman

    worker_id = args.worker_id or f"worker-{args.worker_index + 1}"
    worker_logger = configure_worker_logger(worker_id)
    log_worker_action(
        worker_logger,
        "WORKER_BOOT",
        worker_id=worker_id,
        pid=os.getpid(),
        worker_index=args.worker_index,
        worker_count=args.worker_count,
        patch_status=patch_status,
    )

    server = f"{args.host}:{args.port}"
    worker = gearman.GearmanWorker([server])

    handlers = {
        "demo.analyze": analyze_job,
        "demo.shard": shard_job,
        "demo.bg_log": background_log_job,
    }
    task_names = tuple(task["name"] for task in TASK_CATALOG)
    assigned_list = list(task_names_for_worker(task_names, args.worker_index, args.worker_count))
    if "demo.analyze" not in assigned_list:
        assigned_list.append("demo.analyze")
    assigned_task_names = tuple(assigned_list)
    
    status_reporter = WorkerStatusReporter(
        api_url=args.api_url,
        worker_id=worker_id,
        pid=os.getpid(),
        worker_index=args.worker_index,
        worker_count=args.worker_count,
        registered_tasks=assigned_task_names,
    )
    for task_name in assigned_task_names:
        worker.register_task(
            task_name,
            instrument_handler(task_name, handlers[task_name], worker_id, worker_logger, status_reporter),
        )
        log_worker_action(worker_logger, "TASK_REGISTERED", task=task_name)

    status_reporter.mark_ready(
        details={
            "server": server,
            "tasks": list(assigned_task_names),
            "api_url": args.api_url,
        }
    )
    append_event(
        task="worker.lifecycle",
        stage="worker.register",
        status="ready",
        message=f"{worker_id} registrado en Gearman",
        worker_id=worker_id,
        details={
            "pid": os.getpid(),
            "server": server,
            "worker_index": args.worker_index,
            "worker_count": args.worker_count,
            "tasks": list(assigned_task_names),
        },
    )

    LOGGER.info(
        "%s escuchando en %s con tareas: %s",
        worker_id,
        server,
        ", ".join(assigned_task_names),
    )
    log_worker_action(worker_logger, "WORKER_READY", server=server, tasks=list(assigned_task_names))
    worker.work()


if __name__ == "__main__":
    main()
