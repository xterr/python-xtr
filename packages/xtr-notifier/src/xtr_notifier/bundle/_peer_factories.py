"""The factories of the peer holders, registered only when their peer is active.

Imported by the bundle only once the peer is known to be active, since each
names a type of that peer's package.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from xtr_dependency_injection import Target
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_http_client_contracts import HttpClientInterface

from ._peers import EventDispatcherPeer, HttpClientPeer

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = ["event_dispatcher_peer", "http_client_peer"]


def event_dispatcher_peer(event_dispatcher: EventDispatcherInterface) -> EventDispatcherPeer:
    """Hold the application's default event dispatcher."""
    return EventDispatcherPeer(event_dispatcher)


def http_client_peer(qualifier: str | None) -> Callable[..., HttpClientPeer]:
    """Return the factory holding the HTTP client ``qualifier`` names; ``None`` the default.

    The qualifier is configuration, so the client's annotation is written onto
    the factory at runtime rather than in its signature.
    """

    def build(http_client: HttpClientInterface) -> HttpClientPeer:
        return HttpClientPeer(http_client)

    build.__annotations__ = {
        "http_client": (
            HttpClientInterface
            if qualifier is None
            else Annotated[HttpClientInterface, Target(qualifier)]
        ),
        "return": HttpClientPeer,
    }
    return build
