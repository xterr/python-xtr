"""Hand logging off to a background thread, so a slow handler never blocks a request."""

from __future__ import annotations

import queue
import threading
import traceback
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from .handler_interface import HandlerInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from xtr_logging.log_record import LogRecord

__all__ = ["QueueHandler"]


@final
class _Stop:
    """A marker put on the queue to tell the worker it may finish."""

    __slots__ = ()


_STOP: Final = _Stop()


@final
class QueueHandler(HandlerInterface):
    """Enqueues records and lets a worker thread do the writing.

    Latency-sensitive or async code should not wait on a socket or a disk to
    log a line. This takes the record — safe to hand across threads, since a
    record is immutable — puts it on a queue, and returns at once; a daemon
    thread drains the queue into the wrapped handler.

    A handler failing on the worker must not kill the worker, or every later
    record would be lost silently: the exception goes to ``on_error`` instead,
    which by default prints a traceback to standard error. Call :meth:`flush`
    to wait for the backlog to clear, and :meth:`close` to stop the thread and
    close the wrapped handler; the handler starts a fresh worker if it is used
    again afterwards.
    """

    def __init__(
        self,
        handler: HandlerInterface,
        *,
        max_size: int = 0,
        on_error: Callable[[Exception, LogRecord], None] | None = None,
    ) -> None:
        """Offload ``handler`` onto a background thread.

        Args:
            handler: The handler the worker forwards records to.
            max_size: The most records to hold before :meth:`handle` blocks to
                apply backpressure; ``0`` means an unbounded queue that never
                blocks.
            on_error: Called with any exception the wrapped handler raises on
                the worker, and the record that caused it; a traceback is
                printed to standard error when this is ``None``.
        """
        self._handler: HandlerInterface = handler
        self._on_error: Callable[[Exception, LogRecord], None] | None = on_error
        self._queue: queue.Queue[LogRecord | _Stop] = queue.Queue(maxsize=max_size)
        self._lock: threading.Lock = threading.Lock()
        self._worker: threading.Thread | None = None

    @override
    def is_handling(self, record: LogRecord, /) -> bool:
        """Whether the wrapped handler would handle ``record``."""
        return self._handler.is_handling(record)

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Enqueue ``record`` for the worker and return without waiting.

        Always returns ``False``: the record is only queued, so it must still
        reach the handlers after this one.
        """
        self._ensure_worker()
        self._queue.put(record)
        return False

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Enqueue each record in turn."""
        for record in records:
            _ = self.handle(record)

    def flush(self) -> None:
        """Block until every record queued so far has been handled."""
        self._queue.join()

    @override
    def close(self) -> None:
        """Drain the queue, stop the worker, and close the wrapped handler."""
        self.flush()
        self._stop_worker()
        self._handler.close()

    def _ensure_worker(self) -> None:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                return
            worker = threading.Thread(
                target=self._work,
                name="xtr-logging-queue",
                daemon=True,
            )
            self._worker = worker
            worker.start()

    def _stop_worker(self) -> None:
        with self._lock:
            worker = self._worker
            self._worker = None
        if worker is None:
            return
        self._queue.put(_STOP)
        worker.join()

    def _work(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if isinstance(item, _Stop):
                    return
                try:
                    _ = self._handler.handle(item)
                except Exception as error:  # noqa: BLE001 — one broken record must not kill the worker
                    if self._on_error is not None:
                        self._on_error(error, item)
                    else:
                        traceback.print_exception(error)
            finally:
                self._queue.task_done()
