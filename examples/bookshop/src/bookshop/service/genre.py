"""The genres the shop shelves books under."""

from __future__ import annotations

from enum import StrEnum

__all__ = ["Genre"]


class Genre(StrEnum):
    """Where a book is shelved."""

    FICTION = "fiction"
    SOFTWARE = "software"
    HISTORY = "history"
