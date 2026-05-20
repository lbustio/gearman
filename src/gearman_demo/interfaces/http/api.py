from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from gearman_demo.application.service import GearmanDemoService, GearmanServiceError

from .schemas import AnalyzeRequest, BackgroundLogRequest, PipelineRequest, ShardRequest, WorkerStatusReport

BASE_DIR = Path(__file__).resolve().parent
INDEX_HTML = BASE_DIR.parent / "web" / "index.html"


def create_app(host: str = "127.0.0.1", port: int = 4730) -> FastAPI:
    app = FastAPI(
        title="Gearman Demo API",
        version="0.1.0",
        description="API para gestionar y visualizar tareas del Gearman Demo",
    )
    service = GearmanDemoService(host=host, port=port)

    @app.post("/api/worker-status")
    def report_worker_status(report: WorkerStatusReport) -> dict:
        status = service.update_worker_status(report.model_dump())
        return {"ok": True, "worker_id": status["worker_id"]}

    @app.get("/api/workers-status")
    def get_workers_status() -> list[dict]:
        return service.list_worker_status()

    @app.get("/", response_class=FileResponse)
    def webapp() -> FileResponse:
        return FileResponse(INDEX_HTML)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "gearman_server": service.server}

    @app.get("/api/tasks")
    def tasks() -> list[dict]:
        return service.report()["tasks"]

    @app.post("/api/analyze")
    def analyze(req: AnalyzeRequest) -> dict:
        try:
            return service.run_analyze(text=req.text, top_n=req.top_n)
        except GearmanServiceError as exc:
            raise HTTPException(status_code=502, detail=f"Error en Gearman: {exc}") from exc

    @app.post("/api/shard")
    def shard(req: ShardRequest) -> dict:
        try:
            return service.run_shard(text=req.text, shard_size=req.shard_size)
        except GearmanServiceError as exc:
            raise HTTPException(status_code=502, detail=f"Error en Gearman: {exc}") from exc

    @app.post("/api/background-log")
    def background_log(req: BackgroundLogRequest) -> dict:
        try:
            return service.run_background_log(message=req.message)
        except GearmanServiceError as exc:
            raise HTTPException(status_code=502, detail=f"Error en Gearman: {exc}") from exc

    @app.post("/api/pipeline")
    def pipeline(req: PipelineRequest) -> dict:
        try:
            return service.run_pipeline(text=req.text, shard_size=req.shard_size, top_n=req.top_n)
        except GearmanServiceError as exc:
            raise HTTPException(status_code=502, detail=f"Error en Gearman: {exc}") from exc

    @app.get("/api/jobs")
    def list_jobs() -> list[dict]:
        return service.list_jobs()

    @app.get("/api/events")
    def list_events(limit: int = 100) -> list[dict]:
        return service.list_events(limit=limit)

    @app.get("/api/jobs/{local_job_id}")
    def get_job(local_job_id: str) -> dict:
        job = service.get_job(local_job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        return job

    @app.get("/api/jobs/{local_job_id}/events")
    def get_job_events(local_job_id: str, limit: int = 100) -> list[dict]:
        return service.list_events(local_job_id=local_job_id, limit=limit)

    @app.get("/api/report")
    def report() -> dict:
        return service.report()

    return app
