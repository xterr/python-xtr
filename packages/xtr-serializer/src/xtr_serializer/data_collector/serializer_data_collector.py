"""Every serializer call the request made."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

if TYPE_CHECKING:
    from xtr_http_kernel.data_collector import ProfiledRequest, RequestTrace

    from .serializer_call import SerializerCall

__all__ = ["SerializerDataCollector"]

_NAME: Final = "serializer"


@final
class SerializerDataCollector:
    """Keeps the calls traced serializers recorded for the request, and the counts a toolbar shows.

    The calls are recorded while the request is handled, by each
    :class:`~xtr_serializer.data_collector.TraceableSerializer` writing into the same trace this
    reads; the profiler starts that trace afresh for every profiled request, through
    :meth:`begin_request`. A response that streams may still serialize after it has started, so
    the calls are read again once it has left.
    """

    __slots__ = ("_trace",)

    def __init__(self, trace: RequestTrace[SerializerCall]) -> None:
        """Read the calls recorded into ``trace``."""
        self._trace = trace

    @property
    def name(self) -> str:
        """``"serializer"``."""
        return _NAME

    def begin_request(self) -> None:
        """Start recording the request that just arrived, with no call yet."""
        self._trace.begin()

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the calls so far; those made while the body streams follow."""
        del profiled
        return self._read()

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return every call of the request."""
        del data, profiled
        return self._read()

    def _read(self) -> dict[str, object]:
        calls = self._trace.entries()
        by_method: dict[str, int] = {}
        for call in calls:
            by_method[call["method"]] = by_method.get(call["method"], 0) + 1
        return {
            "calls": [{**call, "context": list(call["context"])} for call in calls],
            "count": len(calls),
            "duration_ms": sum(call["duration_ms"] for call in calls),
            "errors": sum(1 for call in calls if call["error"] is not None),
            "by_method": by_method,
        }
