"""How a purger empties a table."""

from __future__ import annotations

from enum import IntEnum

__all__ = ["PurgeMode"]


class PurgeMode(IntEnum):
    """How a purger empties a table: row by row, or all at once.

    ``DELETE`` works everywhere and inside any transaction. ``TRUNCATE`` is
    faster on a large table and resets its sequences, where the database has
    the statement; elsewhere a purger falls back to ``DELETE``.
    """

    DELETE = 1
    TRUNCATE = 2
