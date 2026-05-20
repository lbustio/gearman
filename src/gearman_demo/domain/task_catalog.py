from __future__ import annotations

from typing import Any


TASK_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "name": "demo.analyze",
        "kind": "analyze",
        "mode": "sync",
        "description": "Tokeniza texto, calcula frecuencia de palabras y sentimiento básico.",
        "input": {"text": "str", "top_n": "int"},
    },
    {
        "name": "demo.shard",
        "kind": "shard",
        "mode": "sync",
        "description": "Divide un texto en shards para simular particionado de trabajo.",
        "input": {"text": "str", "shard_size": "int"},
    },
    {
        "name": "demo.bg_log",
        "kind": "background_log",
        "mode": "background",
        "description": "Acepta telemetría en background sin bloquear al cliente.",
        "input": {"message": "str"},
    },
)


TASK_NAMES = tuple(task["name"] for task in TASK_CATALOG)
