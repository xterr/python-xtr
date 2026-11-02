"""An ``orm://`` DSN names a connection the application does not configure."""

from __future__ import annotations

from .orm_messenger_error import OrmMessengerError

__all__ = ["InvalidOrmDsnError"]


class InvalidOrmDsnError(OrmMessengerError, LookupError):
    """An ``orm://`` DSN names a connection the application does not configure.

    Also a :class:`LookupError`, as a missing key in any other mapping is.

    Attributes:
        transport: The transport whose DSN names it.
        connection: The connection named.
        known: Every connection that is configured.
    """

    transport: str
    connection: str
    known: tuple[str, ...]

    def __init__(self, transport: str, connection: str, known: tuple[str, ...]) -> None:
        """Record the transport, the connection it named and the ones that exist."""
        self.transport = transport
        self.connection = connection
        self.known = known
        names = ", ".join(f'"{each}"' for each in known) or "none"
        super().__init__(
            f'The "{transport}" transport names the connection "{connection}", which is not '
            f"configured; the connections are: {names}."
        )
