"""Where stored clients are read, written, removed and listed."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

    from .client_filter import ClientFilter

__all__ = ["ClientManagerInterface"]


@runtime_checkable
class ClientManagerInterface(Protocol):
    """Reads and writes the stored clients, and lists them on criteria.

    Unlike the credentials this server issues, a client is administered: it is
    registered, amended and withdrawn by a person, which is why this is the
    one manager that removes and lists. Nothing expires, so there is nothing
    to sweep.

    An implementation announces
    :class:`~xtr_security_oauth2_server.event.pre_save_client_event.PreSaveClientEvent`
    before each save, so a rule about clients holds wherever a client comes
    from.
    """

    async def find(self, identifier: str) -> ClientInterface | None:
        """Return the client registered as ``identifier``, or ``None``."""
        ...

    async def save(self, client: ClientInterface) -> None:
        """Store ``client``, announcing it first so a listener may change it."""
        ...

    async def remove(self, client: ClientInterface) -> None:
        """Forget ``client``; forgetting one that was never stored is no error."""
        ...

    async def list(self, client_filter: ClientFilter | None) -> Sequence[ClientInterface]:
        """Return the clients meeting ``client_filter``, or every one for ``None``.

        A filter that names nothing lists every client too, so a caller
        building criteria from options it was given need not check whether it
        ended up with any.
        """
        ...
