"""The ``audit_trail`` middleware: a container-built class, named with ``@as_middleware``."""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Target
from xtr_logging_contracts import LoggerInterface
from xtr_messenger import (
    Envelope,
    MiddlewareInterface,
    ReceivedStamp,
    StackInterface,
    TransportNamesStamp,
    as_middleware,
)

__all__ = ["AuditTrailMiddleware"]


@final
@as_middleware("audit_trail")
class AuditTrailMiddleware(MiddlewareInterface):
    """Writes where every dispatch went to the ``security`` channel.

    A container-built class: its constructor is injected like any service's.
    """

    def __init__(self, logger: Annotated[LoggerInterface, Target("security")]) -> None:
        """Write to ``logger``."""
        self._logger = logger

    @override
    async def handle(self, envelope: Envelope, stack: StackInterface, /) -> Envelope:
        result = await stack.next().handle(envelope, stack)
        forced = envelope.last(TransportNamesStamp)
        self._logger.info(
            "{message} dispatched{received}",
            {
                "message": type(envelope.message).__name__,
                "received": " (received)" if envelope.last(ReceivedStamp) else "",
                "forced_transports": forced.transport_names if forced else None,
            },
        )
        return result
