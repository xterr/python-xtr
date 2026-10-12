"""Clients kept in this process, announced before each save."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_event_dispatcher_contracts import (  # noqa: TC002 -- container hydrates this constructor at runtime
    EventDispatcherInterface,
)

from xtr_security_oauth2_server.event.pre_save_client_event import PreSaveClientEvent
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.oauth2_events import OAuth2Events

if TYPE_CHECKING:
    from collections.abc import Iterable, Sequence

    from xtr_security_oauth2_server.manager.client_filter import ClientFilter
    from xtr_security_oauth2_server.model.client_interface import ClientInterface

__all__ = ["ClientManager"]


@final
class ClientManager(ClientManagerInterface):
    """Holds the registered clients in a mapping, for one process.

    For tests and single-process demonstrations. It announces every save, like
    every other client manager, so a listener written against a stored
    deployment behaves the same here — which is what makes a demonstration
    worth anything.

    A listing narrows the same way a stored one does: a client has to hold
    every value named, of every kind named.
    """

    def __init__(self, dispatcher: EventDispatcherInterface) -> None:
        """Announce each save through ``dispatcher``."""
        self._dispatcher = dispatcher
        self._clients: dict[str, ClientInterface] = {}

    @override
    def __repr__(self) -> str:
        """Name the type and how many clients are held, never which."""
        return f"{type(self).__name__}(held={len(self._clients)})"

    @override
    async def find(self, identifier: str) -> ClientInterface | None:
        """Return the client registered as ``identifier``, or ``None``."""
        return self._clients.get(identifier)

    @override
    async def save(self, client: ClientInterface) -> None:
        """Announce ``client``, then store whatever the event ends up holding."""
        event = await self._dispatcher.dispatch(
            PreSaveClientEvent(client),
            OAuth2Events.PRE_SAVE_CLIENT,
        )
        stored = event.get_client()
        self._clients[stored.get_identifier()] = stored

    @override
    async def remove(self, client: ClientInterface) -> None:
        """Forget ``client``; forgetting one that was never stored is no error."""
        _ = self._clients.pop(client.get_identifier(), None)

    @override
    async def list(self, client_filter: ClientFilter | None) -> Sequence[ClientInterface]:
        """Return the clients meeting ``client_filter``, or every one for ``None``."""
        if client_filter is None or not client_filter.has_filters():
            return tuple(self._clients.values())

        return tuple(client for client in self._clients.values() if _meets(client, client_filter))


def _meets(client: ClientInterface, client_filter: ClientFilter) -> bool:
    """Tell whether ``client`` meets every kind of criterion the filter names."""
    return (
        _holds_every(client.get_grants(), client_filter.get_grants())
        and _holds_every(client.get_scopes(), client_filter.get_scopes())
        and _holds_every(client.get_redirect_uris(), client_filter.get_redirect_uris())
    )


def _holds_every(held: Iterable[object], wanted: Sequence[object]) -> bool:
    """Tell whether ``held`` has all of ``wanted``; naming nothing asks for nothing.

    Compared as strings, so a criterion built from a plain value object
    matches a client whose own value objects came back from storage as
    different instances.
    """
    by_name = {str(value) for value in held}

    return all(str(value) in by_name for value in wanted)
