from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_MAX_WORKERS = 64


@dataclass(frozen=True)
class WorkerAssignment:
    worker_index: int
    worker_count: int
    task_names: tuple[str, ...]


def detected_cpu_count() -> int:
    return os.cpu_count() or 1


def effective_worker_count(cpu_count: int | None = None, max_workers: int = DEFAULT_MAX_WORKERS) -> int:
    if max_workers <= 0:
        raise ValueError("max_workers debe ser mayor a 0")
    available_cpus = cpu_count if cpu_count is not None else detected_cpu_count()
    return max(1, min(available_cpus, max_workers))


def assign_tasks_to_workers(task_names: tuple[str, ...], worker_count: int) -> tuple[WorkerAssignment, ...]:
    if worker_count <= 0:
        raise ValueError("worker_count debe ser mayor a 0")
    if not task_names:
        raise ValueError("Debe existir al menos una tarea")

    assignments: list[list[str]] = [[] for _ in range(worker_count)]
    if len(task_names) >= worker_count:
        for task_index, task_name in enumerate(task_names):
            assignments[task_index % worker_count].append(task_name)
    else:
        for worker_index in range(worker_count):
            assignments[worker_index].append(task_names[worker_index % len(task_names)])

    return tuple(
        WorkerAssignment(
            worker_index=worker_index,
            worker_count=worker_count,
            task_names=tuple(worker_tasks),
        )
        for worker_index, worker_tasks in enumerate(assignments)
    )


def task_names_for_worker(task_names: tuple[str, ...], worker_index: int, worker_count: int) -> tuple[str, ...]:
    if worker_index < 0 or worker_index >= worker_count:
        raise ValueError("worker_index debe estar dentro del rango de workers")
    return assign_tasks_to_workers(task_names, worker_count)[worker_index].task_names
