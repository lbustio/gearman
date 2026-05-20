from __future__ import annotations

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
