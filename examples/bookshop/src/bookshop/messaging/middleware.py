"""Middleware, three ways: named with ``@as_middleware``, and an instance in the config.

The configuration's ``middleware`` list names what runs, in order, ahead of routing and
handling. A name is resolved from the container — ``"logging"`` is the messenger bundle's,
``"audit_trail"`` and ``"timing"`` / ``"stopwatch"`` are declared here — and an object is
used as it is (see :class:`MaintenanceGuard`, built in ``bookshop.config.messenger``).

Middleware keeps no per-message state: one instance serves every dispatch, concurrently,
on the bus and in every worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, final

from typing_extensions import override
from xtr_clock import MonotonicClock
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

from .messages import PlaceOrder
from .stamps import DispatchTimeStamp, MaintenanceStamp

__all__ = ["AuditTrailMiddleware", "MaintenanceGuard", "TimingMiddleware"]


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


@final
@as_middleware("timing")
@as_middleware("stopwatch")
class TimingMiddleware(MiddlewareInterface):
    """Stamps how long the rest of the chain took.

    Declared under two names — the decorator is repeatable, and each name reaches the same
    class. Durations come from a monotonic clock.
    """

    def __init__(self) -> None:
        """Measure with a monotonic clock."""
        self._clock = MonotonicClock()

    @override
    async def handle(self, envelope: Envelope, stack: StackInterface, /) -> Envelope:
        started = self._clock.now()
        result = await stack.next().handle(envelope, stack)
        elapsed = (self._clock.now() - started).total_seconds() * 1000
        return result.with_stamps(DispatchTimeStamp(elapsed))


@final
@dataclass(frozen=True, slots=True)
class MaintenanceGuard(MiddlewareInterface):
    """Refuses new orders while the shop is in maintenance — built in the config.

    Its ``enabled`` field is an ``env("SHOP_MAINTENANCE", bool, ...)`` placeholder while the
    kernel builds; the container resolves the whole config, this dataclass included, before
    the bus receives it. Returning the envelope without calling the next middleware
    short-circuits the chain: nothing downstream runs.

    Attributes:
        enabled: Whether to refuse.
    """

    enabled: bool

    @override
    async def handle(self, envelope: Envelope, stack: StackInterface, /) -> Envelope:
        if self.enabled and isinstance(envelope.message, PlaceOrder):
            return envelope.with_stamps(MaintenanceStamp("the shop is in maintenance"))
        return await stack.next().handle(envelope, stack)
