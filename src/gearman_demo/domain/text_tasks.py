from __future__ import annotations

import re
from collections import Counter
from typing import Any

TOKEN_RE = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9']+")

POSITIVE_WORDS = {
    "excelente",
    "genial",
    "fantastico",
    "fantástico",
    "feliz",
    "rapido",
    "rápido",
    "estable",
    "seguro",
    "productivo",
    "increible",
    "increíble",
    "bueno",
    "great",
    "awesome",
}

NEGATIVE_WORDS = {
    "lento",
    "falla",
    "error",
    "caida",
    "caída",
    "malo",
    "terrible",
    "bug",
    "inestable",
    "horrible",
    "fatal",
}


def normalize_tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def shard_text(text: str, shard_size: int) -> list[str]:
    if shard_size <= 0:
        raise ValueError("shard_size debe ser mayor a 0")
    return [text[index : index + shard_size] for index in range(0, len(text), shard_size)]


def compress_text(text: str) -> str:
    tokens = normalize_tokens(text)
    if not tokens:
        return ""

    compressed: list[str] = []
    current = tokens[0]
    count = 1
    for token in tokens[1:]:
        if token == current:
            count += 1
            continue
        compressed.append(f"{current}:{count}")
        current = token
        count = 1
    compressed.append(f"{current}:{count}")
    return "|".join(compressed)


def analyze_text(text: str, top_n: int = 5) -> dict[str, Any]:
    tokens = normalize_tokens(text)
    counter = Counter(tokens)

    positive = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negative = sum(1 for token in tokens if token in NEGATIVE_WORDS)

    return {
        "chars": len(text),
        "tokens": len(tokens),
        "unique_tokens": len(counter),
        "top_tokens": counter.most_common(top_n),
        "sentiment": {
            "positive": positive,
            "negative": negative,
            "score": positive - negative,
        },
        "compression_preview": compress_text(text[:200]),
    }
