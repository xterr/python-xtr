"""What the mailer's services take from optional peers, present or not.

A peer bundle may be inactive — no HTTP client installed, no event dispatcher, no message bus,
no rate limiter, no logging — and a container cannot inject what it does not hold. So each peer
reaches the services through a holder the bundle always registers: built from the peer's service
when the peer is active, holding ``None`` otherwise. The services then take one fixed set of
parameters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mailer._error_text import shown
from xtr_mailer.exception import LogicError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_dependency_injection import ServiceLocator
    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpClientInterface
    from xtr_logging_contracts import LoggerInterface
    from xtr_messenger import MessageBusInterface
    from xtr_rate_limiter import RateLimiterFactoryInterface

__all__ = [
    "MAILER_CHANNEL",
    "EventDispatcherPeer",
    "HttpClientPeer",
    "LoggerPeer",
    "MessageBusPeer",
    "RateLimitersPeer",
]

#: The logging channel the transports and the listeners write to.
MAILER_CHANNEL: Final = "mailer"


@final
class HttpClientPeer:
    """The HTTP client provider transports are reached through, or ``None`` without one."""

    __slots__: ClassVar[tuple[str, ...]] = ("http_client",)

    def __init__(self, http_client: HttpClientInterface | None) -> None:
        """Hold ``http_client``."""
        self.http_client: HttpClientInterface | None = http_client


@final
class EventDispatcherPeer:
    """Where emails are announced, or ``None`` without an event dispatcher."""

    __slots__: ClassVar[tuple[str, ...]] = ("event_dispatcher",)

    def __init__(self, event_dispatcher: EventDispatcherInterface | None) -> None:
        """Hold ``event_dispatcher``."""
        self.event_dispatcher: EventDispatcherInterface | None = event_dispatcher


@final
class LoggerPeer:
    """Where the transports and the listeners log, or ``None`` to log nothing."""

    __slots__: ClassVar[tuple[str, ...]] = ("logger",)

    def __init__(self, logger: LoggerInterface | None) -> None:
        """Hold ``logger``."""
        self.logger: LoggerInterface | None = logger


@final
class MessageBusPeer:
    """The bus emails are queued on, or ``None`` to send each at once."""

    __slots__: ClassVar[tuple[str, ...]] = ("message_bus",)

    def __init__(self, message_bus: MessageBusInterface | None) -> None:
        """Hold ``message_bus``."""
        self.message_bus: MessageBusInterface | None = message_bus


@final
class RateLimitersPeer:
    """The configured rate limiters by name, or ``None`` without the rate limiter bundle."""

    __slots__: ClassVar[tuple[str, ...]] = ("_rate_limiters",)

    def __init__(self, rate_limiters: ServiceLocator[RateLimiterFactoryInterface] | None) -> None:
        """Hold ``rate_limiters``."""
        self._rate_limiters = rate_limiters

    async def capping(
        self, limiter_names: Mapping[str, str]
    ) -> dict[str, RateLimiterFactoryInterface]:
        """Return the limiter capping each transport, from the limiter name of each.

        Raises:
            LogicError: A transport names a limiter that is not configured.
        """
        capping: dict[str, RateLimiterFactoryInterface] = {}
        for transport, limiter in limiter_names.items():
            if self._rate_limiters is None or limiter not in self._rate_limiters:
                raise LogicError(
                    f'The "{shown(transport)}" transport is capped by the "{shown(limiter)}" '
                    "rate limiter, which is not configured."
                )
            capping[transport] = await self._rate_limiters.get(limiter)
        return capping
