from __future__ import annotations

import array
import socket
import ssl
from typing import Any


def apply_gearman3_python312_patch() -> None:
    """Patch gearman3 compatibility issues on modern Python."""
    patch_array_fromstring()
    patch_worker_task_bytes()


def gearman3_patch_status() -> dict[str, bool]:
    import gearman.connection
    import gearman.worker_handler

    return {
        "array_fromstring": getattr(gearman.connection.GearmanConnection, "_gearman_demo_py312_patch", False),
        "task_bytes": getattr(gearman.worker_handler.GearmanWorkerCommandHandler, "_gearman_demo_task_bytes_patch", False),
    }


def patch_array_fromstring() -> None:
    if hasattr(array.array("b"), "fromstring"):
        return

    import gearman.connection

    connection_class = gearman.connection.GearmanConnection
    if getattr(connection_class, "_gearman_demo_py312_patch", False):
        return

    def read_data_from_socket(self: Any, bytes_to_read: int = 4096) -> int:
        if not self.connected:
            self.throw_exception(message="disconnected")

        while True:
            try:
                recv_buffer = self.gearman_socket.recv(bytes_to_read)
            except ssl.SSLError as exc:
                if exc.errno in [ssl.SSL_ERROR_WANT_READ, ssl.SSL_ERROR_WANT_WRITE]:
                    continue
                self.throw_exception(exception=exc)
            except socket.error as socket_exception:
                self.throw_exception(exception=socket_exception)

            if len(recv_buffer) == 0:
                self.throw_exception(message="remote disconnected")
            break

        if self.use_ssl:
            remaining = self.gearman_socket.pending()
            while remaining:
                recv_buffer += self.gearman_socket.recv(remaining)
                remaining = self.gearman_socket.pending()

        self._incoming_buffer.frombytes(recv_buffer)
        return len(self._incoming_buffer)

    connection_class.read_data_from_socket = read_data_from_socket
    connection_class._gearman_demo_py312_patch = True


def patch_worker_task_bytes() -> None:
    import gearman.worker_handler
    from gearman.errors import InvalidWorkerState

    handler_class = gearman.worker_handler.GearmanWorkerCommandHandler
    if getattr(handler_class, "_gearman_demo_task_bytes_patch", False):
        return

    def recv_job_assign_uniq(self: Any, job_handle: Any, task: Any, unique: Any, data: Any) -> bool:
        if isinstance(task, bytes):
            task = task.decode("utf-8")

        assert task in self._handler_abilities, "%s not found in %r" % (task, self._handler_abilities)

        if not self.connection_manager.check_job_lock(self):
            raise InvalidWorkerState("Received a job when we weren't expecting one")

        gearman_job = self.connection_manager.create_job(self, job_handle, task, unique, self.decode_data(data))
        self.connection_manager.on_job_execute(gearman_job)
        self._release_job_lock()
        self._sleep()
        return True

    handler_class.recv_job_assign_uniq = recv_job_assign_uniq
    handler_class._gearman_demo_task_bytes_patch = True
