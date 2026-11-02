"""Telling apart what a driver's error means, whichever database raised it.

Each database reports a deadlock, a lock it gave up waiting for or a missing
table its own way — PostgreSQL with an SQLSTATE, MySQL with an error number,
SQLite only in its message — and the driver's error is all SQLAlchemy hands
back. Reading it in one place keeps every caller to one question.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from sqlalchemy.exc import DBAPIError

__all__ = ["is_missing_table", "is_retryable"]

_RETRYABLE_SQLSTATES: Final = frozenset({"40001", "40P01", "55P03"})
"""Serialization failure, deadlock, lock not available."""

_RETRYABLE_MYSQL_CODES: Final = frozenset({1205, 1213})
"""Lock wait timeout, deadlock."""

_RETRYABLE_MESSAGES: Final = ("database is locked", "database table is locked")
"""SQLite, whose errors carry no code a driver exposes."""

_MISSING_TABLE_SQLSTATE: Final = "42P01"
_MISSING_TABLE_MYSQL_CODE: Final = 1146
_MISSING_TABLE_MESSAGE: Final = "no such table"


def is_retryable(error: DBAPIError) -> bool:
    """Tell whether ``error`` is a conflict with another transaction, worth trying again.

    Workers claiming messages from one table run into each other: a deadlock,
    a lock they waited too long for. Neither says anything about the message,
    so the same statement a moment later goes through.
    """
    original = error.orig
    return (
        _sqlstate(original) in _RETRYABLE_SQLSTATES
        or _mysql_code(original) in _RETRYABLE_MYSQL_CODES
        or any(text in str(original) for text in _RETRYABLE_MESSAGES)
    )


def is_missing_table(error: DBAPIError) -> bool:
    """Tell whether ``error`` says the table the statement names does not exist."""
    original = error.orig
    return (
        _sqlstate(original) == _MISSING_TABLE_SQLSTATE
        or _mysql_code(original) == _MISSING_TABLE_MYSQL_CODE
        or _MISSING_TABLE_MESSAGE in str(original)
    )


def _sqlstate(original: BaseException | None) -> str | None:
    """Return the SQLSTATE a PostgreSQL driver put on its error, if any."""
    state: object = getattr(original, "sqlstate", None)
    return state if isinstance(state, str) else None


def _mysql_code(original: BaseException | None) -> int | None:
    """Return the error number a MySQL driver put first in its error's arguments, if any."""
    if original is None:
        return None
    arguments: tuple[object, ...] = original.args
    if not arguments:
        return None
    first = arguments[0]
    return first if isinstance(first, int) and not isinstance(first, bool) else None
