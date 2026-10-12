"""A client is about to be stored, and may still be changed."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_security_oauth2_server.model.client_interface import ClientInterface

__all__ = ["PreSaveClientEvent"]


class PreSaveClientEvent(Event):
    """Carries the client a manager is about to store.

    Announced by every client manager, whatever it stores clients in, so a
    rule about clients is written once and holds for a client registered by a
    command, by an administration screen or by a test fixture alike.

    A listener may change the client in place, or put a different one on the
    event — which is what the setter is for — and the manager stores whatever
    the event holds when the last listener has run.

    Not final: an application that wants its own event for its own client
    class may derive from it, and the manager will still store what the event
    carries.
    """

    def __init__(self, client: ClientInterface) -> None:
        """Announce that ``client`` is about to be stored."""
        self._client: ClientInterface = client

    def get_client(self) -> ClientInterface:
        """Return the client to be stored."""
        return self._client

    def set_client(self, client: ClientInterface) -> None:
        """Store ``client`` instead of the one announced."""
        self._client = client

    @override
    def __repr__(self) -> str:
        """Name the event and the client, whose own reading holds no secret."""
        return f"{type(self).__name__}(client={self._client!r})"
