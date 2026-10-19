"""The one production reading of the current instant.

A remember-me handler times its cookies — when they expire, when a stored
value was last used — and takes the reader as a constructor argument so a
test can freeze it. This is the reading the argument falls back to.
"""

from __future__ import annotations

from datetime import UTC, datetime

__all__ = ["system_now"]


def system_now() -> datetime:
    """Return the current instant, timezone-aware."""
    return datetime.now(UTC)
