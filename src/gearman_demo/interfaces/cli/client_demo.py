from __future__ import annotations

import argparse
import json

import gearman

from gearman_demo.gearman.compat import apply_gearman3_python312_patch
from gearman_demo.gearman.client import submit_background_job, submit_sync_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Cliente de demostración Gearman")
    parser.add_argument("text", help="Texto a procesar")
    parser.add_argument("--host", default="127.0.0.1", help="Host del job server Gearman")
    parser.add_argument("--port", type=int, default=4730, help="Puerto del job server Gearman")
    parser.add_argument("--top-n", type=int, default=5, help="Cantidad de tokens top")
    parser.add_argument("--shard-size", type=int, default=80, help="Tamaño de cada shard")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    server = f"{args.host}:{args.port}"
    apply_gearman3_python312_patch()
    client = gearman.GearmanClient([server])

    analyze = submit_sync_job(client, "demo.analyze", {"text": args.text, "top_n": args.top_n})
    shard = submit_sync_job(client, "demo.shard", {"text": args.text, "shard_size": args.shard_size})
    bg_handle = submit_background_job(
        client,
        "demo.bg_log",
        {"message": f"Procesado texto de {len(args.text)} chars con top_n={args.top_n}"},
    )

    print("=== ANALYZE ===")
    print(json.dumps(analyze, ensure_ascii=False, indent=2))
    print("\n=== SHARD ===")
    print(json.dumps(shard, ensure_ascii=False, indent=2))
    print("\n=== BACKGROUND ===")
    print(f"Job handle: {bg_handle}")


if __name__ == "__main__":
    main()
