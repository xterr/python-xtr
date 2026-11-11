"""The table runs are kept in."""

from __future__ import annotations

from typing import Final

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Index,
    MetaData,
    SmallInteger,
    String,
    Table,
    Text,
)
from sqlalchemy.dialects.mysql import DATETIME, LONGTEXT

__all__ = ["DEFAULT_TABLE_PREFIX", "run_table"]

DEFAULT_TABLE_PREFIX: Final = "ai_"
"""What the table name starts with unless told otherwise."""

_ID: Final = 64
_NAME: Final = 255

# MySQL's TEXT holds 64 KB and its DATETIME keeps whole seconds.
_JSON: Final = Text().with_variant(LONGTEXT(), "mysql")
_INSTANT: Final = DateTime(timezone=False).with_variant(DATETIME(fsp=6), "mysql")


def run_table(metadata: MetaData, table_prefix: str = DEFAULT_TABLE_PREFIX) -> Table:
    """Return ``{prefix}run`` in ``metadata``, adding it first where it is not there.

    ``active_key`` holds the conversation of a running top-level run and is
    empty otherwise; its unique index is what lets one such run per
    conversation in at a time, on every database — empty values never collide,
    so no partial index is needed.
    """
    name = f"{table_prefix}run"
    found = metadata.tables.get(name)
    if found is not None:
        return found
    return Table(
        name,
        metadata,
        Column("run_id", String(_ID), primary_key=True),
        Column("agent", String(_NAME), nullable=False),
        Column("conversation_id", String(_NAME), nullable=True),
        Column("parent_run_id", String(_ID), nullable=True),
        Column("state", SmallInteger, nullable=False),
        Column("cancel_requested", Boolean, nullable=False),
        Column("usage", _JSON, nullable=True),
        Column("metadata", _JSON, nullable=False),
        Column("started_at", _INSTANT, nullable=False),
        Column("heartbeat_at", _INSTANT, nullable=False),
        Column("finished_at", _INSTANT, nullable=True),
        Column("active_key", String(_NAME), nullable=True, unique=True),
        Index(None, "conversation_id"),
    )
