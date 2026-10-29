"""The processor the logging config names by id — see ``memory_handler`` for every id."""

from __future__ import annotations

from contextvars import ContextVar
from typing import Final, final

from typing_extensions import override
from xtr_dependency_injection import as_alias, as_service
from xtr_logging import LogRecord, ProcessorInterface

__all__ = ["REQUEST_ID", "RequestIdProcessor"]

REQUEST_ID: Final[ContextVar[str | None]] = ContextVar("bookshop_request_id", default=None)
"""The id of the request or command being handled; set by the web server and commands."""


@final
@as_alias(ProcessorInterface, qualifier="request")
@as_service
class RequestIdProcessor(ProcessorInterface):
    """Adds the current request id to every record.

    Registered under its own class by ``@as_service``, and reachable as
    ``(ProcessorInterface, "request")`` through ``@as_alias`` — which is the key a
    ``ServiceProcessorConfig(id="request")`` is resolved from.
    """

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        request_id = REQUEST_ID.get()
        return record if request_id is None else record.with_extra({"request_id": request_id})
