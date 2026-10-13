"""How a value is named in the message that refuses it."""

from __future__ import annotations

__all__ = ["debug_type"]


def debug_type(value: object) -> str:
    """Name the type of ``value`` the way an error message should.

    ``None`` is named ``null`` because that is what a caller wrote, or what a
    JSON document carried; everything else is named by its class.
    """
    return "null" if value is None else type(value).__name__
