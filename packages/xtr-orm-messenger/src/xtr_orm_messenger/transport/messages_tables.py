"""Which messages tables a bus configuration keeps on a connection."""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from .orm_options import ORM_SCHEME, OrmOptions

if TYPE_CHECKING:
    from xtr_messenger import MessageBusConfig

__all__ = ["messages_tables"]


def messages_tables(
    config: MessageBusConfig, connection: str, default_connection: str
) -> tuple[str, ...]:
    """Return the tables the ``orm://`` transports of ``config`` keep on ``connection``.

    What a connection's migrations need to write each transport's table like
    one of the application's own: a transport naming no connection is on
    ``default_connection``. Each table is named once, in the order its first
    transport is configured.

    Raises:
        InvalidDsnError: When a transport's DSN carries no scheme.
        UnknownTransportOptionError: When an ``orm://`` transport carries a
            setting it does not accept.
        InvalidTransportOptionError: When a setting's value is not what it
            takes.
    """
    found: dict[str, None] = {}
    for transport in config.transports.values():
        dsn = transport.parsed
        if dsn.scheme != ORM_SCHEME:
            continue
        if (urlsplit(dsn.connection).netloc or default_connection) != connection:
            continue
        found[OrmOptions.from_settings(transport.settings).table_name] = None
    return tuple(found)
