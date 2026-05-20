import array
import pathlib
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gearman_demo.gearman.compat import apply_gearman3_python312_patch, gearman3_patch_status


class GearmanCompatTestCase(unittest.TestCase):
    def test_apply_python312_patch(self) -> None:
        apply_gearman3_python312_patch()

        import gearman.connection

        if not hasattr(array.array("b"), "fromstring"):
            self.assertTrue(getattr(gearman.connection.GearmanConnection, "_gearman_demo_py312_patch", False))
        self.assertTrue(gearman3_patch_status()["task_bytes"])

    def test_patched_read_data_from_socket_uses_frombytes(self) -> None:
        apply_gearman3_python312_patch()

        import gearman.connection

        class FakeSocket:
            def recv(self, bytes_to_read: int) -> bytes:
                return b"abc"

        connection = SimpleNamespace(
            connected=True,
            gearman_socket=FakeSocket(),
            use_ssl=False,
            _incoming_buffer=array.array("b"),
            throw_exception=lambda **kwargs: (_ for _ in ()).throw(RuntimeError(kwargs)),
        )

        bytes_read = gearman.connection.GearmanConnection.read_data_from_socket(connection)

        self.assertEqual(bytes_read, 3)
        self.assertEqual(connection._incoming_buffer.tobytes(), b"abc")

    def test_patched_worker_handler_accepts_task_bytes(self) -> None:
        apply_gearman3_python312_patch()

        import gearman.worker_handler

        handler = gearman.worker_handler.GearmanWorkerCommandHandler()
        handler._handler_abilities = ["demo.shard"]
        handler.decode_data = lambda data: data
        handler._release_job_lock = Mock(return_value=True)
        handler._sleep = Mock(return_value=True)
        handler.connection_manager = Mock()
        handler.connection_manager.check_job_lock.return_value = True
        handler.connection_manager.create_job.return_value = object()

        result = handler.recv_job_assign_uniq(
            job_handle=b"H:127.0.0.1:1",
            task=b"demo.shard",
            unique=None,
            data=b"{}",
        )

        self.assertTrue(result)
        handler.connection_manager.create_job.assert_called_once()
        self.assertEqual(handler.connection_manager.create_job.call_args.args[2], "demo.shard")


if __name__ == "__main__":
    unittest.main()
