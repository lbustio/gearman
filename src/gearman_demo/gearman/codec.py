from __future__ import annotations

import json
from typing import Any


def encode_payload(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def decode_payload(data: bytes | str) -> dict[str, Any]:
    if isinstance(data, bytes):
        data = data.decode("utf-8")
    payload = json.loads(data)
    if not isinstance(payload, dict):
        raise ValueError("El payload del job debe ser un objeto JSON")
    return payload


def decode_result(result: bytes | str | None) -> dict[str, Any]:
    if not result:
        return {}
    if isinstance(result, bytes):
        result = result.decode("utf-8")
    data = json.loads(result)
    if not isinstance(data, dict):
        raise ValueError("El resultado del job debe ser un objeto JSON")
    return data
