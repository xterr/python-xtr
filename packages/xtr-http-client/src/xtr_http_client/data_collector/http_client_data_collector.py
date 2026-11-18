"""Every outgoing HTTP request the profiled request made."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final, TypedDict, final

from xtr_http_kernel.data_collector import RequestTrace, clone_var

from ._masking import MASK, masked, masked_header_line, sensitive_header

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import RequestOptions
    from xtr_http_kernel.data_collector import ProfiledRequest

    from xtr_http_client.traceable_http_client import TracedRequest

__all__ = ["HttpClientDataCollector"]

_NAME: Final = "http_client"
_FAILED_STATUS: Final = 400
_MS_PER_SECOND: Final = 1000.0


class _RequestData(TypedDict):
    client: str
    method: str
    url: str
    status: int | None
    duration_ms: float | None
    error: str | None
    request_headers: list[str]
    request_body: dict[str, object] | None
    response_headers: list[str]
    response_size: int | None
    content_traced: bool


@final
class HttpClientDataCollector:
    """Keeps every request the clients made while the profiled request was handled.

    A tracing client hands :meth:`record` each request's live record as it is
    made; the record goes on filling in as the answer and its body arrive, so
    it is read once the response has left, when they have. The records belong
    to the request being profiled — two served at once each see their own —
    and nothing is kept outside one. Credentials — an ``Authorization`` or a
    cookie header, a body field named like a password, a secret or a token —
    are kept as ``******``.
    """

    __slots__ = ("_trace",)

    def __init__(self) -> None:
        """Record nothing until a profiled request begins."""
        self._trace: RequestTrace[tuple[str, TracedRequest]] = RequestTrace(_NAME)

    @property
    def name(self) -> str:
        """``"http_client"``."""
        return _NAME

    def begin_request(self) -> None:
        """Start recording the profiled request that just arrived."""
        self._trace.begin()

    def is_recording(self) -> bool:
        """Tell whether a profiled request is being recorded in the calling context."""
        return self._trace.is_recording()

    def record(self, client: str, traced: TracedRequest) -> None:
        """Keep ``traced``, made through the client service ``client``, for the request."""
        self._trace.record((client, traced))

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the requests so far; the rest of them follows once the response has left."""
        del profiled
        return self._read()

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return every request, with the answers and bodies that have arrived since."""
        del data, profiled
        return self._read()

    def _read(self) -> dict[str, object]:
        requests = [_request(client, traced) for client, traced in self._trace.entries()]
        durations = [entry["duration_ms"] for entry in requests]
        return {
            "requests": requests,
            "count": len(requests),
            "errors": sum(1 for entry in requests if _failed(entry)),
            "duration_ms": sum(duration for duration in durations if duration is not None),
        }


def _request(client: str, traced: TracedRequest) -> _RequestData:
    info = traced["info"]
    options = traced["options"]
    content = traced["content"]
    kept = content is not False
    url = info.get("url")
    status = info.get("http_code")
    total = info.get("total_time")
    error = info.get("error")
    return {
        "client": client,
        "method": traced["method"],
        "url": url if isinstance(url, str) else traced["url"],
        "status": status if isinstance(status, int) and not isinstance(status, bool) else None,
        "duration_ms": (
            total * _MS_PER_SECOND
            if isinstance(total, int | float) and not isinstance(total, bool)
            else None
        ),
        "error": error if isinstance(error, str) else None,
        "request_headers": _request_headers(options),
        "request_body": _request_body(options) if kept else None,
        "response_headers": _response_headers(info),
        "response_size": len(content) if isinstance(content, bytes) else None,
        "content_traced": kept,
    }


def _failed(entry: _RequestData) -> bool:
    status = entry["status"]
    return entry["error"] is not None or (status is not None and status >= _FAILED_STATUS)


def _request_headers(options: RequestOptions) -> list[str]:
    lines: list[str] = []
    for name, value in options.get("headers", {}).items():
        values = [value] if isinstance(value, str) else list(value)
        lines += [f"{name}: {MASK if sensitive_header(name) else item}" for item in values]
    return lines


def _request_body(options: RequestOptions) -> dict[str, object] | None:
    if "json" in options:
        return clone_var(masked(options["json"]))
    if "body" in options:
        return clone_var(masked(options["body"]))
    return None


def _response_headers(info: Mapping[str, object]) -> list[str]:
    lines = info.get("response_headers")
    if not isinstance(lines, Sequence) or isinstance(lines, str):
        return []
    return [masked_header_line(line) for line in lines if isinstance(line, str)]
