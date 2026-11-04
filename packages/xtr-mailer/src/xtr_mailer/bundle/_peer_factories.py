"""The factories of the peer holders, registered only when their peer is active.

Imported by the bundle only once a peer is known to be active, since each names a type of that
peer's package — the rate limiter's in a module of its own, as it may be absent alone.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_client_contracts import HttpClientInterface
from xtr_logging_contracts import LoggerInterface

from ._peers import MAILER_CHANNEL, EventDispatcherPeer, HttpClientPeer, LoggerPeer

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["event_dispatcher_peer", "http_client_peer", "logger_peer"]


def event_dispatcher_peer(event_dispatcher: EventDispatcherInterface) -> EventDispatcherPeer:
    """Hold the application's default event dispatcher."""
    return EventDispatcherPeer(event_dispatcher)


def logger_peer(logger: Annotated[LoggerInterface, Target(MAILER_CHANNEL)]) -> LoggerPeer:
    """Hold the logger of the mailer's own channel."""
    return LoggerPeer(logger)


def http_client_peer(qualifier: str | None) -> Callable[..., HttpClientPeer]:
    """Return the factory holding the HTTP client ``qualifier`` names; ``None`` the default.

    The qualifier is configuration, so the client's annotation is written onto the factory at
    runtime rather than in its signature.
    """

    def mailer_http_client(http_client: HttpClientInterface) -> HttpClientPeer:
        return HttpClientPeer(http_client)

    mailer_http_client.__annotations__ = {
        "http_client": (
            HttpClientInterface
            if qualifier is None
            else Annotated[HttpClientInterface, Target(qualifier)]
        ),
        "return": HttpClientPeer,
    }
    return mailer_http_client
