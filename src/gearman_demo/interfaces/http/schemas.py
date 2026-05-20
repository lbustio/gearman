from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    text: str = Field(min_length=1, description="Texto a analizar")
    top_n: int = Field(default=5, ge=1, le=50)


class ShardRequest(BaseModel):
    text: str = Field(min_length=1, description="Texto a dividir")
    shard_size: int = Field(default=120, ge=1, le=2000)


class BackgroundLogRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


class PipelineRequest(BaseModel):
    text: str = Field(min_length=1, description="Texto a dividir y analizar por shard")
    shard_size: int = Field(default=120, ge=1, le=2000)
    top_n: int = Field(default=5, ge=1, le=50)


class WorkerStatusReport(BaseModel):
    worker_id: str = Field(description="Identificador único del worker")
    pid: int = Field(ge=0)
    worker_index: int = Field(ge=0)
    worker_count: int = Field(ge=1)
    status: str = Field(description="ready, busy, idle, failed, stopped")
    busy: bool
    jobs_in_progress: int = Field(ge=0)
    jobs_processed: int = Field(ge=0)
    jobs_failed: int = Field(ge=0)
    current_task: str | None = None
    current_job_id: str | None = None
    current_gearman_handle: str | None = None
    last_job_type: str | None = None
    last_job_started_at: str | None = None
    last_job_finished_at: str | None = None
    last_duration_ms: float | None = None
    registered_tasks: list[str] = Field(default_factory=list)
    updated_at: str
    details: dict[str, Any] = Field(default_factory=dict)
