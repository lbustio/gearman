import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gearman_demo.gearman.worker_assignment import (
    assign_tasks_to_workers,
    effective_worker_count,
    task_names_for_worker,
)


class WorkerAssignmentTestCase(unittest.TestCase):
    def test_effective_worker_count_is_capped(self) -> None:
        self.assertEqual(effective_worker_count(cpu_count=128, max_workers=64), 64)
        self.assertEqual(effective_worker_count(cpu_count=0, max_workers=64), 1)

    def test_more_tasks_than_workers_assigns_multiple_tasks_per_worker(self) -> None:
        assignments = assign_tasks_to_workers(("a", "b", "c", "d", "e"), worker_count=2)

        self.assertEqual(assignments[0].task_names, ("a", "c", "e"))
        self.assertEqual(assignments[1].task_names, ("b", "d"))

    def test_more_workers_than_tasks_reuses_tasks_round_robin(self) -> None:
        assignments = assign_tasks_to_workers(("a", "b", "c"), worker_count=5)

        self.assertEqual([item.task_names for item in assignments], [("a",), ("b",), ("c",), ("a",), ("b",)])

    def test_task_names_for_worker(self) -> None:
        task_names = task_names_for_worker(("a", "b", "c"), worker_index=4, worker_count=5)

        self.assertEqual(task_names, ("b",))


if __name__ == "__main__":
    unittest.main()
