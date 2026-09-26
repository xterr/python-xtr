"""Services the logging config refers to by id.

A ``ServiceHandlerSpec(id=...)``, a ``ServiceProcessorSpec(id=...)``, a handler's string
``formatter`` and a fingers-crossed ``activation_strategy`` each name a service the
application registers under the matching interface, *qualified by that id*:

======================================  =================================  ====================
Config entry                            Registered as                      Id
======================================  =================================  ====================
``ServiceHandlerSpec(id="memory")``     ``(HandlerInterface, "memory")``   factory, qualified
``formatter="audit_json"``              ``(FormatterInterface, ...)``      factory, qualified
``activation_strategy="security"``      ``(ActivationStrategyInterface…)`` factory, qualified
``ServiceProcessorSpec(id="request")``  ``(ProcessorInterface, ...)``      class + ``@as_alias``
======================================  =================================  ====================

A missing id fails the build — the logging bundle checks every one in its ``process`` hook.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Final, final

from typing_extensions import override
from xtr_dependency_injection import as_alias, as_service
from xtr_logging import (
    ActivationStrategyInterface,
    ChannelLevelActivationStrategy,
    FormatterInterface,
    HandlerInterface,
    JsonBatchMode,
    JsonFormatter,
    LogRecord,
    ProcessorInterface,
    TestHandler,
)

__all__ = [
    "REQUEST_ID",
    "RequestIdProcessor",
    "audit_formatter",
    "memory_handler",
    "security_strategy",
]

REQUEST_ID: Final[ContextVar[str | None]] = ContextVar("bookshop_request_id", default=None)
"""The id of the request or command being handled; set by the web server and commands."""


@as_service(qualifier="memory")
def memory_handler() -> HandlerInterface:
    """Keep the last records in memory — ``bookshop logs:recent`` prints them."""
    return TestHandler()


@as_service(qualifier="audit_json")
def audit_formatter() -> FormatterInterface:
    """Render audit records as JSON lines; the ``audit_file`` handler names it as a string."""
    return JsonFormatter(JsonBatchMode.NEWLINES, include_stacktraces=True)


@as_service(qualifier="security")
def security_strategy() -> ActivationStrategyInterface:
    """Trigger a fingers-crossed flush at WARNING on ``security``, at ERROR elsewhere."""
    return ChannelLevelActivationStrategy("error", {"security": "warning"})


@final
@as_alias(ProcessorInterface, qualifier="request")
@as_service
class RequestIdProcessor(ProcessorInterface):
    """Adds the current request id to every record.

    Registered under its own class by ``@as_service``, and reachable as
    ``(ProcessorInterface, "request")`` through ``@as_alias`` — which is the key a
    ``ServiceProcessorSpec(id="request")`` is resolved from.
    """

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        request_id = REQUEST_ID.get()
        return record if request_id is None else record.with_extra({"request_id": request_id})
