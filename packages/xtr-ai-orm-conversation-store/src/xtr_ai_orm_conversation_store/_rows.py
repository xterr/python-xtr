"""Turning records and entries into rows and back."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Final, Literal, cast

import pydantic
from pydantic_ai import DeferredToolRequests
from pydantic_ai.conversation_store import ConversationEntry, ConversationRecord
from pydantic_ai.messages import ModelMessage
from pydantic_ai.usage import RunUsage

if TYPE_CHECKING:
    from sqlalchemy import Row

__all__ = ["entry_from_row", "entry_row", "record_from_row", "record_row"]

# Bytes travel as base64 in both directions, as pydantic-ai's own message adapter does.
_JSON: Final = pydantic.ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")
_MESSAGE: Final = pydantic.TypeAdapter[ModelMessage](ModelMessage, config=_JSON)
_USAGE: Final = pydantic.TypeAdapter(RunUsage)
_DEFERRED: Final = pydantic.TypeAdapter(DeferredToolRequests)
_BRANCHES: Final = pydantic.TypeAdapter(list[str])


def record_row(record: ConversationRecord) -> dict[str, Any]:
    """The ``conversation`` row holding ``record``."""
    deferred = record.deferred_tool_requests
    return {
        "conversation_id": record.conversation_id,
        "head_id": record.head_id,
        "scope": record.scope,
        "usage": _USAGE.dump_json(record.usage).decode(),
        "deferred_tool_requests": _DEFERRED.dump_json(deferred).decode() if deferred else None,
        "forked_from": record.forked_from,
        "forked_at": record.forked_at,
        "branches": _BRANCHES.dump_json(record.branches).decode(),
        "revision": record.revision,
        "updated_at": _naive_utc(record.updated_at),
        "format_version": record.format_version,
    }


def record_from_row(row: Row[Any]) -> ConversationRecord:
    """The record a ``conversation`` row holds."""
    deferred = cast("str | None", row.deferred_tool_requests)
    updated_at = cast("datetime", row.updated_at)
    return ConversationRecord(
        conversation_id=cast("str", row.conversation_id),
        head_id=cast("str | None", row.head_id),
        usage=_USAGE.validate_json(cast("str", row.usage)),
        deferred_tool_requests=_DEFERRED.validate_json(deferred) if deferred else None,
        scope=cast("str | None", row.scope),
        forked_from=cast("str | None", row.forked_from),
        forked_at=cast("str | None", row.forked_at),
        branches=_BRANCHES.validate_json(cast("str", row.branches)),
        revision=cast("str", row.revision),
        updated_at=updated_at.replace(tzinfo=UTC),
        format_version=cast("Literal[1]", row.format_version),
    )


def entry_row(entry: ConversationEntry) -> dict[str, Any]:
    """The ``conversation_entry`` row holding ``entry``."""
    return {
        "id": entry.id,
        "parent_id": entry.parent_id,
        "kind": entry.kind,
        "message": _MESSAGE.dump_json(entry.message).decode(),
    }


def entry_from_row(row: Row[Any]) -> ConversationEntry:
    """The entry a ``conversation_entry`` row holds."""
    return ConversationEntry(
        id=cast("str", row.id),
        parent_id=cast("str | None", row.parent_id),
        message=_MESSAGE.validate_json(cast("str", row.message)),
        kind=cast("Literal['message']", row.kind),
    )


def _naive_utc(instant: datetime) -> datetime:
    """``instant``'s UTC wall clock without a zone, as a zone-less column keeps it everywhere."""
    utc = instant.astimezone(UTC)
    return datetime(  # noqa: DTZ001 — a zone-less column wants exactly a naive value
        utc.year, utc.month, utc.day, utc.hour, utc.minute, utc.second, utc.microsecond
    )
