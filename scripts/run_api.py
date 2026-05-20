import argparse

import uvicorn

from gearman_demo.interfaces.http.api import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Servidor FastAPI para Gearman Demo")
    parser.add_argument("--host", default="127.0.0.1", help="Host del server Gearman")
    parser.add_argument("--port", type=int, default=4730, help="Puerto del server Gearman")
    parser.add_argument("--api-host", default="0.0.0.0", help="Host para exponer FastAPI")
    parser.add_argument("--api-port", type=int, default=8000, help="Puerto para exponer FastAPI")
    parser.add_argument("--reload", action="store_true", help="Activa autoreload de uvicorn")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    app = create_app(host=args.host, port=args.port)
    uvicorn.run(app, host=args.api_host, port=args.api_port, reload=args.reload)


if __name__ == "__main__":
    main()
