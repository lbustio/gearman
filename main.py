from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gearman_demo.domain.task_catalog import TASK_NAMES
from gearman_demo.gearman.telemetry import EVENT_LOG_ENV, WORKER_LOG_DIR_ENV, reset_event_log
from gearman_demo.gearman.worker_assignment import (
    DEFAULT_MAX_WORKERS,
    assign_tasks_to_workers,
    detected_cpu_count,
    effective_worker_count,
)


def cpu_worker_id(worker_index: int) -> str:
    return f"cpu-{worker_index + 1:02d}"


def reexec_with_venv() -> None:
    if not VENV_PYTHON.exists():
        return
    if Path(sys.executable).resolve() == VENV_PYTHON.resolve():
        return
    os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), *sys.argv])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Levanta Gearman Demo completo")
    parser.add_argument("--gearman-host", default="127.0.0.1", help="Host del job server Gearman")
    parser.add_argument("--gearman-port", type=int, default=4730, help="Puerto del job server Gearman")
    parser.add_argument("--api-host", default="127.0.0.1", help="Host para exponer FastAPI")
    parser.add_argument("--api-port", type=int, default=8000, help="Puerto preferido para FastAPI")
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Cantidad exacta de workers. Por defecto usa la cantidad de CPUs detectadas",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=DEFAULT_MAX_WORKERS,
        help="Tope de workers cuando se detectan CPUs automáticamente",
    )
    parser.add_argument(
        "--no-start-gearmand",
        action="store_true",
        help="No intenta iniciar gearmand; requiere que ya esté escuchando",
    )
    return parser


def process_env() -> dict[str, str]:
    env = os.environ.copy()
    current = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(SRC_DIR) if not current else f"{SRC_DIR}{os.pathsep}{current}"
    env["PYTHONUNBUFFERED"] = "1"
    env[EVENT_LOG_ENV] = str(PROJECT_ROOT / ".runtime" / "events.jsonl")
    env[WORKER_LOG_DIR_ENV] = str(PROJECT_ROOT / ".runtime" / "workers")
    return env


def is_port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((host, port)) == 0
    except PermissionError as exc:
        raise RuntimeError("El entorno no permite abrir sockets para verificar puertos") from exc


def wait_for_port(host: str, port: int, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_port_open(host, port):
            return True
        time.sleep(0.1)
    return False


def next_available_port(host: str, preferred: int) -> int:
    for port in range(preferred, preferred + 50):
        if not is_port_open(host, port):
            return port
    raise RuntimeError(f"No hay puertos libres cerca de {preferred}")


def local_api_url(host: str, port: int) -> str:
    report_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{report_host}:{port}"


def start_process(
    name: str,
    command: list[str],
    env: dict[str, str],
    startup_delay: float = 0.35,
) -> subprocess.Popen:
    print(f"[main] Iniciando {name}: {' '.join(command)}", flush=True)
    process = subprocess.Popen(command, cwd=PROJECT_ROOT, env=env)
    time.sleep(startup_delay)
    if process.poll() is not None:
        raise RuntimeError(f"{name} terminó inmediatamente con código {process.returncode}")
    return process


def resolved_worker_count(args: argparse.Namespace) -> int:
    if args.workers is not None:
        if args.workers <= 0:
            raise RuntimeError("--workers debe ser mayor a 0")
        if args.workers > DEFAULT_MAX_WORKERS:
            raise RuntimeError(f"--workers no puede ser mayor a {DEFAULT_MAX_WORKERS}")
        return args.workers
    return effective_worker_count(cpu_count=detected_cpu_count(), max_workers=args.max_workers)


def start_gearmand(args: argparse.Namespace) -> subprocess.Popen | None:
    if is_port_open(args.gearman_host, args.gearman_port):
        print(f"[main] Gearman ya está escuchando en {args.gearman_host}:{args.gearman_port}", flush=True)
        return None

    if args.no_start_gearmand:
        raise RuntimeError(
            f"No hay Gearman escuchando en {args.gearman_host}:{args.gearman_port}. "
            "Inícialo manualmente o quita --no-start-gearmand."
        )

    gearmand = shutil.which("gearmand")
    if gearmand is None:
        raise RuntimeError(
            "No encontré el binario 'gearmand'. Instálalo primero, por ejemplo: "
            "sudo apt install gearman-job-server"
        )

    process = subprocess.Popen(
        [
            gearmand,
            f"--listen={args.gearman_host}",
            f"--port={args.gearman_port}",
            "--verbose",
            "INFO",
        ],
        cwd=PROJECT_ROOT,
    )
    if not wait_for_port(args.gearman_host, args.gearman_port, timeout=5):
        process.terminate()
        raise RuntimeError("gearmand no abrió el puerto esperado")
    print(f"[main] Gearman iniciado en {args.gearman_host}:{args.gearman_port}", flush=True)
    return process


def terminate_processes(processes: list[tuple[str, subprocess.Popen | None]]) -> None:
    for name, process in reversed(processes):
        if process is None or process.poll() is not None:
            continue
        print(f"[main] Deteniendo {name}", flush=True)
        process.terminate()

    for _, process in reversed(processes):
        if process is None:
            continue
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def run() -> int:
    args = build_parser().parse_args()
    env = process_env()
    worker_count = resolved_worker_count(args)
    api_port = next_available_port(args.api_host, args.api_port)
    api_url = local_api_url(args.api_host, api_port)
    env["GEARMAN_DEMO_API_URL"] = api_url
    if api_port != args.api_port:
        print(f"[main] Puerto {args.api_port} ocupado; usaré {api_port} para la API", flush=True)

    processes: list[tuple[str, subprocess.Popen | None]] = []
    try:
        reset_event_log(Path(env[EVENT_LOG_ENV]))
        Path(env[WORKER_LOG_DIR_ENV]).mkdir(parents=True, exist_ok=True)
        print(
            f"[main] CPUs detectadas: {detected_cpu_count()} | workers a levantar: {worker_count}",
            flush=True,
        )
        for assignment in assign_tasks_to_workers(TASK_NAMES, worker_count):
            print(
                "[main] Worker "
                f"{assignment.worker_index + 1}/{assignment.worker_count}: "
                f"{', '.join(assignment.task_names)}",
                flush=True,
            )

        gearmand_process = start_gearmand(args)
        processes.append(("gearmand", gearmand_process))

        api_process = start_process(
            "api",
            [
                sys.executable,
                "scripts/run_api.py",
                "--host",
                args.gearman_host,
                "--port",
                str(args.gearman_port),
                "--api-host",
                args.api_host,
                "--api-port",
                str(api_port),
            ],
            env,
        )
        processes.append(("api", api_process))

        if wait_for_port(args.api_host, api_port, timeout=5):
            print(f"[main] Web lista en http://{args.api_host}:{api_port}/", flush=True)
            print(f"[main] Swagger en http://{args.api_host}:{api_port}/docs", flush=True)
        else:
            raise RuntimeError("La API no abrió el puerto esperado")

        for worker_index in range(worker_count):
            worker_process = start_process(
                f"worker-{worker_index + 1}",
                [
                    sys.executable,
                    "scripts/run_worker.py",
                    "--host",
                    args.gearman_host,
                    "--port",
                    str(args.gearman_port),
                    "--worker-index",
                    str(worker_index),
                    "--worker-count",
                    str(worker_count),
                    "--worker-id",
                    cpu_worker_id(worker_index),
                    "--api-url",
                    api_url,
                ],
                env,
                startup_delay=0.05,
            )
            processes.append((f"worker-{worker_index + 1}", worker_process))

        print("[main] Presiona Ctrl-C para detener todo", flush=True)
        while True:
            for name, process in processes:
                if process is not None and process.poll() is not None:
                    raise RuntimeError(f"{name} terminó con código {process.returncode}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[main] Apagando servicios", flush=True)
        return 0
    except Exception as exc:
        print(f"[main] Error: {exc}", file=sys.stderr, flush=True)
        return 1
    finally:
        terminate_processes(processes)


def main() -> None:
    reexec_with_venv()
    raise SystemExit(run())


if __name__ == "__main__":
    main()
