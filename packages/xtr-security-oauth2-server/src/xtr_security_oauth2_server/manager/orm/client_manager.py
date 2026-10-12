"""Clients in a database, announced before each save and listed on criteria."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from sqlalchemy import Text, or_, select
from sqlalchemy import cast as as_text
from typing_extensions import override
from xtr_event_dispatcher_contracts import (
    EventDispatcherInterface,  # noqa: TC002 — read at runtime by the container
)
from xtr_orm import ConnectionRegistry  # noqa: TC002 — read at runtime by the container

from xtr_security_oauth2_server.event.pre_save_client_event import PreSaveClientEvent
from xtr_security_oauth2_server.manager.client_manager_interface import ClientManagerInterface
from xtr_security_oauth2_server.model.abstract_client import (
    AbstractClient,  # noqa: TC001 — read at runtime by the container
)
from xtr_security_oauth2_server.oauth2_events import OAuth2Events
from xtr_security_oauth2_server.persistence.mapping.mapped_table import mapped_table

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy import Table
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql.elements import ColumnElement

    from xtr_security_oauth2_server.manager.client_filter import ClientFilter
    from xtr_security_oauth2_server.model.client_interface import ClientInterface

__all__ = ["ClientManager"]

_ESCAPE: Final = "\\"
"""What takes a wildcard's meaning away, so a criterion matches itself only."""


@final
class ClientManager(ClientManagerInterface):
    """Reads and writes the registered clients, and lists them on criteria.

    A client is administered rather than issued, so this is the one manager
    that removes and lists, and the one with nothing to sweep. Every save is
    announced first, exactly as the in-process manager announces it, so a rule
    about clients holds wherever a client comes from — and every write is
    committed, so a client registered by a command or by a request is stored
    before the caller is told it was.

    A client is read by its identifier and not by the primary key of its
    table: an application's own client class may have a key of its own, with
    the identifier a unique column beside it.

    Listing works on the columns as they are stored: a client's grants, scopes
    and redirect URIs each live in one space-separated column, so a criterion
    is matched against the whole value or against a value with a space on
    either side of it. Every value named has to be held — a listing narrowed
    by two grants holds the clients registered for both — and so has every
    kind of criterion named.

    One of these serves the whole application, and holds no session: every
    read and every write asks the connection registry for the session of the
    request being served.
    """

    def __init__(
        self,
        connections: ConnectionRegistry,
        connection: str,
        dispatcher: EventDispatcherInterface,
        client_class: type[AbstractClient],
    ) -> None:
        """Read and write the clients of the connection named ``connection``.

        Args:
            connections: Where the session of the unit of work under way is
                asked for.
            connection: Which connection's session that is.
            dispatcher: What each save is announced through.
            client_class: The class a client row is read into.
        """
        self._connections = connections
        self._connection = connection
        self._dispatcher = dispatcher
        self._client_class = client_class

    async def _session(self) -> AsyncSession:
        """Return the session of the unit of work this request is served in."""
        return await self._connections.session(self._connection)

    @override
    async def find(self, identifier: str) -> ClientInterface | None:
        """Return the client registered as ``identifier``, or ``None``."""
        clients = mapped_table(self._client_class)
        read = await (await self._session()).execute(
            select(self._client_class).where(clients.c["identifier"] == identifier),
        )

        return read.scalars().one_or_none()

    @override
    async def save(self, client: ClientInterface) -> None:
        """Announce ``client``, then store whatever the event ends up holding."""
        event = await self._dispatcher.dispatch(
            PreSaveClientEvent(client),
            OAuth2Events.PRE_SAVE_CLIENT,
        )
        session = await self._session()
        session.add(event.get_client())
        await session.commit()

    @override
    async def remove(self, client: ClientInterface) -> None:
        """Forget ``client``, which has to be one this unit of work knows."""
        session = await self._session()
        await session.delete(client)
        await session.commit()

    @override
    async def list(self, client_filter: ClientFilter | None) -> Sequence[ClientInterface]:
        """Return the clients meeting ``client_filter``, or every one for ``None``."""
        clients = mapped_table(self._client_class)
        read = await (await self._session()).execute(
            select(self._client_class).where(*_criteria(clients, client_filter)),
        )

        return tuple(read.scalars().all())


def _criteria(
    clients: Table,
    client_filter: ClientFilter | None,
) -> tuple[ColumnElement[bool], ...]:
    """Return one condition per value ``client_filter`` names, of every kind."""
    if client_filter is None or not client_filter.has_filters():
        return ()
    named = (
        ("grants", client_filter.get_grants()),
        ("redirect_uris", client_filter.get_redirect_uris()),
        ("scopes", client_filter.get_scopes()),
    )

    return tuple(_holds(clients, column, value) for column, values in named for value in values)


def _holds(clients: Table, column: str, value: object) -> ColumnElement[bool]:
    """Return a condition met by a client whose ``column`` holds ``value``.

    The column is read as plain text, so a criterion is compared with the
    string that is stored rather than being bound as the list it stands for.
    """
    stored = as_text(clients.c[column], Text())
    written = str(value)
    pattern = _literally(written)

    return or_(
        stored == written,
        stored.like(f"% {pattern}", escape=_ESCAPE),
        stored.like(f"{pattern} %", escape=_ESCAPE),
        stored.like(f"% {pattern} %", escape=_ESCAPE),
    )


def _literally(value: str) -> str:
    """Return ``value`` with every wildcard taken to mean itself.

    A grant or a scope holds neither of the two wildcards, but a redirect URI
    may hold a percent sign in an escape, and a listing narrowed by one of
    those must not quietly hold every client.
    """
    escaped = value.replace(_ESCAPE, _ESCAPE * 2)

    return escaped.replace("%", f"{_ESCAPE}%").replace("_", f"{_ESCAPE}_")
