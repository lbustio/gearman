"""Dominio puro: tareas y contratos sin dependencias de Gearman o FastAPI."""

from .text_tasks import analyze_text, compress_text, shard_text

__all__ = ["analyze_text", "compress_text", "shard_text"]
