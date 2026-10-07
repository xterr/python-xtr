"""Hand logging off to a background thread, so a slow handler never blocks a request."""

from __future__ import annotations

import queue
import threading
import traceback
from contextvars import copy_context
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_service_contracts import ResetInterface

from xtr_logging.log_context import current_context
from xtr_logging.log_unit import in_unit

from .handler_interface import HandlerInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from contextvars import Context

    from xtr_logging.log_record import LogRecord

__all__ = ["QueueHandler"]


@final
class _Stop:
    """A marker put on the queue to tell the worker it may finish."""

    __slots__ = ()


_STOP: Final = _Stop()

_WORKER_CHECK_INTERVAL: Final = 0.1
"""Seconds a flush waits between checks that the worker it waits on is still alive."""


@final
class QueueHandler(HandlerInterface, ResetInterface):
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

    Closing is serialised: a second :meth:`close` waits for the first rather
    than racing it for the worker, and a record logged while a close runs waits
    for it to finish, then goes to the fresh worker — it is never stranded on a
    queue nothing drains. What the worker itself logs while stopping is written
    before the wrapped handler closes.
    """

    def __init__(
        self,
        handler: HandlerInterface,
        *,
        max_size: int = 10_000,
        on_error: Callable[[Exception, LogRecord], None] | None = None,
    ) -> None:
        """Offload ``handler`` onto a background thread.

        Args:
            handler: The handler the worker forwards records to.
            max_size: The most records to hold before :meth:`handle` blocks to
                apply backpressure; ``0`` means an unbounded queue that never
                blocks. Bounded at ``10_000`` by default, so a worker that
                cannot keep up applies backpressure rather than growing without
                limit.
            on_error: Called with any exception the wrapped handler raises on
                the worker, and the record that caused it; a traceback is
                printed to standard error when this is ``None``.
        """
        self._handler: HandlerInterface = handler
        self._on_error: Callable[[Exception, LogRecord], None] | None = on_error
        self._queue: queue.Queue[tuple[LogRecord, Context | None] | _Stop] = queue.Queue(
            maxsize=max_size
        )
        self._state: threading.Condition = threading.Condition(threading.Lock())
        self._close_lock: threading.Lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._closing: bool = False
        self._putting: int = 0

    @override
    def is_handling(self, record: LogRecord, /) -> bool:
        """Whether the wrapped handler would handle ``record``."""
        return self._handler.is_handling(record)

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Enqueue ``record`` for the worker and return without waiting.

        The caller's context is captured alongside the record only when there
        is logging state to carry — a unit of work is open, or the ambient log
        context is bound — so the worker writes it in the same unit it was
        logged from: a fingers-crossed handler behind the queue keeps a
        request's buffer for that request, not for whichever record the worker
        happens to drain next. With nothing bound there is nothing to copy, and
        the capture is skipped.

        Always returns ``False``: the record is only queued, so it must still
        reach the handlers after this one.
        """
        with self._state:
            # The worker logging into its own queue while stopping must not
            # wait for the stop it is holding up.
            while self._closing and threading.current_thread() is not self._worker:
                _ = self._state.wait()
            self._start_worker()
            self._putting += 1
        try:
            context = copy_context() if in_unit() or current_context() else None
            self._queue.put((record, context))
        finally:
            with self._state:
                self._putting -= 1
                self._state.notify_all()
        return False

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Enqueue each record in turn."""
        for record in records:
            _ = self.handle(record)

    def flush(self) -> None:
        """Block until every record queued so far has been handled.

        A worker that died — a handler raising what is not an ``Exception``
        — is started again while waiting, or the records it left would never
        be handled and this would wait forever.
        """
        done = self._queue.all_tasks_done
        while True:
            # Started outside ``with done``: ``done`` shares the queue's mutex
            # with ``get()`` and ``task_done()``, so a worker started while it
            # is held could not drain anything until ``wait()`` released it.
            self._ensure_worker()
            with done:
                if not self._queue.unfinished_tasks:
                    return
                _ = done.wait(_WORKER_CHECK_INTERVAL)

    @override
    def reset(self) -> None:
        """Handle every record queued so far, then reset the wrapped handler.

        What the wrapped handler buffered for one unit of work — a
        fingers-crossed request log — must not reach the next.
        """
        self.flush()
        if isinstance(self._handler, ResetInterface):
            self._handler.reset()

    @override
    def close(self) -> None:
        """Drain the queue, stop the worker, and close the wrapped handler."""
        with self._close_lock:
            self.flush()
            self._stop_worker()
            self._handler.close()

    def _ensure_worker(self) -> None:
        with self._state:
            self._start_worker()

    def _start_worker(self) -> None:
        """Start a worker unless one runs or a close is stopping it; the caller holds ``_state``."""
        if self._closing:
            return
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
        with self._state:
            # No worker may start while the running one is being stopped, or a
            # concurrent flush would leave a fresh worker behind close().
            self._closing = True
            # A record already on its way in lands ahead of the stop marker.
            while self._putting:
                _ = self._state.wait()
            worker = self._worker
        try:
            if worker is not None:
                self._queue.put(_STOP)
                worker.join()
            # The worker is gone: what it logged behind the marker is written
            # here, before the wrapped handler closes.
            self._drain()
        finally:
            with self._state:
                self._worker = None
                self._closing = False
                self._state.notify_all()

    def _drain(self) -> None:
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                return
            try:
                if not isinstance(item, _Stop):
                    self._write(*item)
            finally:
                self._queue.task_done()

    def _report(self, error: Exception, record: LogRecord) -> None:
        """Hand ``error`` to ``on_error``; print it, and ``on_error``'s own failure, otherwise."""
        if self._on_error is None:
            traceback.print_exception(error)
            return
        try:
            self._on_error(error, record)
        except Exception as failure:  # noqa: BLE001 — a failing error callback must not kill the worker
            traceback.print_exception(error)
            traceback.print_exception(failure)

    def _write(self, record: LogRecord, context: Context | None) -> None:
        try:
            if context is None:
                _ = self._handler.handle(record)
            else:
                _ = context.run(self._handler.handle, record)
        except Exception as error:  # noqa: BLE001 — one broken record must not kill the worker
            self._report(error, record)

    def _work(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if isinstance(item, _Stop):
                    return
                self._write(*item)
            finally:
                self._queue.task_done()
