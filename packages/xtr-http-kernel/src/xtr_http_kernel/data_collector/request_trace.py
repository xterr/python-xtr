"""What one profiled request recorded, kept apart from every other request served at once."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Generic, TypeVar, final

__all__ = ["RequestTrace"]

_EntryT = TypeVar("_EntryT")


@final
class _Entries(Generic[_EntryT]):
    """One request's entries, appended to in place so a copied context adds to the same list."""

    __slots__ = ("items",)

    def __init__(self) -> None:
        self.items: list[_EntryT] = []


@final
class RequestTrace(Generic[_EntryT]):
    """Records entries for the profiled request being served, and nothing outside one.

    A library's instrumentation — a query listener, a decorated client, an event
    listener — records into a trace; its data collector reads the trace back
    when the profile is collected. One process serves many requests at once, so
    the entries belong to the calling context: :meth:`begin` starts the request's
    own list — the profiler calls it, through
    :class:`~xtr_http_kernel.data_collector.TracingDataCollectorInterface`, as a
    profiled request arrives — and every :meth:`record` made while that request
    is handled goes there, from a worker thread running a synchronous endpoint
    too. Outside a profiled request, recording does nothing, so the
    instrumentation costs a lookup and keeps nothing.

    ```python
    queries: RequestTrace[dict[str, object]] = RequestTrace("orm_queries")
    queries.begin()
    queries.record({"sql": "SELECT 1"})
    queries.entries()  # ({"sql": "SELECT 1"},)
    ```
    """

    __slots__ = ("_current",)

    def __init__(self, name: str) -> None:
        """Make a trace named ``name``, after what it records."""
        self._current: ContextVar[_Entries[_EntryT] | None] = ContextVar(
            f"request_trace_{name}", default=None
        )

    def begin(self) -> None:
        """Start recording the calling context's request, from nothing."""
        _ = self._current.set(_Entries())

    def is_recording(self) -> bool:
        """Tell whether a profiled request is being recorded in the calling context."""
        return self._current.get() is not None

    def record(self, entry: _EntryT) -> None:
        """Keep ``entry`` for the request being recorded; do nothing outside one."""
        entries = self._current.get()
        if entries is not None:
            entries.items.append(entry)

    def entries(self) -> tuple[_EntryT, ...]:
        """Return what the calling context's request recorded, oldest first."""
        entries = self._current.get()
        return tuple(entries.items) if entries is not None else ()
