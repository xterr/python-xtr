"""The table an ``orm://`` transport keeps its messages in."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Column, DateTime, Index, Integer, String, Table, Text

if TYPE_CHECKING:
    from sqlalchemy import MetaData

__all__ = ["messages_table"]


def messages_table(metadata: MetaData, table_name: str) -> Table:
    """Add the messages table ``table_name`` to ``metadata``, or return the one already there.

    One definition serves the transport, its setup and the migrations a
    connection writes, so the three never disagree on a column. Every instant
    is stored as a naive UTC datetime: the one form every database compares
    the same way.

    The index follows the query a worker asks — a queue's messages that are
    due and not handed out, oldest first.
    """
    existing = metadata.tables.get(table_name)
    if existing is not None:
        return existing
    return Table(
        table_name,
        metadata,
        Column(
            "id",
            BigInteger().with_variant(Integer(), "sqlite"),
            primary_key=True,
            autoincrement=True,
        ),
        Column("body", Text(), nullable=False),
        Column("headers", Text(), nullable=False),
        Column("queue_name", String(190), nullable=False),
        Column("created_at", DateTime(), nullable=False),
        Column("available_at", DateTime(), nullable=False),
        Column("delivered_at", DateTime(), nullable=True),
        Index(
            f"{table_name}_queue_name_idx",
            "queue_name",
            "available_at",
            "delivered_at",
            "id",
        ),
    )
