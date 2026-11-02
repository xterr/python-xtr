"""Configuration for the orm messenger bundle."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_orm_messenger.transport.orm_options import DEFAULT_TABLE_NAME, OrmOptions

__all__ = ["OrmMessengerConfig"]


@dataclass(frozen=True, slots=True)
class OrmMessengerConfig:
    """Whether the messages table joins a connection's migrations, and under which name.

    Attributes:
        migrations_connection: The connection whose migrations write the
            messages table, or ``None`` to leave the table to the transport,
            which creates it the first time it runs unless ``auto_setup=false``.
        table_name: The table the transports keep their messages in — the
            ``table_name`` their DSNs give, the default when they give none.
    """

    migrations_connection: str | None = None
    table_name: str = DEFAULT_TABLE_NAME

    def __post_init__(self) -> None:
        """Refuse a table name no transport could use, or an empty connection name.

        Raises:
            InvalidTransportOptionError: When ``table_name`` is not a plain
                identifier.
            ValueError: When ``migrations_connection`` is empty.
        """
        _ = OrmOptions(table_name=self.table_name)
        if self.migrations_connection == "":
            message = "migrations_connection names no connection; leave it None to map nothing"
            raise ValueError(message)
