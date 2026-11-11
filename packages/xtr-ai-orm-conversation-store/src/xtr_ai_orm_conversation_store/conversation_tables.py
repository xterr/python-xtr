"""The two tables a conversation is stored in."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, final

from sqlalchemy import Column, DateTime, Index, MetaData, SmallInteger, String, Table, Text
from sqlalchemy.dialects.mysql import DATETIME, LONGTEXT

__all__ = ["DEFAULT_TABLE_PREFIX", "ConversationTables"]

DEFAULT_TABLE_PREFIX: Final = "ai_"
"""What both table names start with unless told otherwise."""

_ID: Final = 64
_NAME: Final = 255

# MySQL's TEXT holds 64 KB, less than one message carrying an image, and its DATETIME keeps
# whole seconds, which leaves conversations saved in the same second unordered.
_JSON: Final = Text().with_variant(LONGTEXT(), "mysql")
_INSTANT: Final = DateTime(timezone=False).with_variant(DATETIME(fsp=6), "mysql")


@final
@dataclass(frozen=True, slots=True)
class ConversationTables:
    """``{prefix}conversation``, a row per conversation; ``{prefix}conversation_entry``, a message.

    An entry holds one message and points at the entry before it; entries are
    shared between a conversation and its forks, so they carry no conversation
    of their own. Every structured value is pydantic's JSON, as text, so binary
    content keeps its base64 form on every database.
    """

    conversation: Table
    entry: Table

    @classmethod
    def define(
        cls, metadata: MetaData, table_prefix: str = DEFAULT_TABLE_PREFIX
    ) -> ConversationTables:
        """Return the tables in ``metadata``, adding them first where they are not there."""
        conversation_name = f"{table_prefix}conversation"
        entry_name = f"{table_prefix}conversation_entry"
        conversation = metadata.tables.get(conversation_name)
        if conversation is None:
            conversation = Table(
                conversation_name,
                metadata,
                Column("conversation_id", String(_NAME), primary_key=True),
                Column("head_id", String(_ID), nullable=True),
                Column("scope", String(_NAME), nullable=True),
                Column("usage", _JSON, nullable=False),
                Column("deferred_tool_requests", _JSON, nullable=True),
                Column("forked_from", String(_NAME), nullable=True),
                Column("forked_at", String(_ID), nullable=True),
                Column("branches", _JSON, nullable=False),
                Column("revision", String(_ID), nullable=False),
                Column("updated_at", _INSTANT, nullable=False),
                Column("format_version", SmallInteger, nullable=False),
                Index(None, "scope", "updated_at"),
                Index(None, "forked_from"),
            )
        entry = metadata.tables.get(entry_name)
        if entry is None:
            entry = Table(
                entry_name,
                metadata,
                Column("id", String(_ID), primary_key=True),
                Column("parent_id", String(_ID), nullable=True),
                Column("kind", String(32), nullable=False),
                Column("message", _JSON, nullable=False),
                Index(None, "parent_id"),
            )
        return cls(conversation=conversation, entry=entry)
