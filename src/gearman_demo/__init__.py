"""Proyecto demostrativo de Gearman con procesamiento de texto."""

from .domain.text_tasks import analyze_text, compress_text, shard_text

__all__ = ["analyze_text", "compress_text", "shard_text"]
