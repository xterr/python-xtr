"""The library's base error."""

from __future__ import annotations

__all__ = ["FulltextError"]


class FulltextError(Exception):
    """Every error this library raises derives from this one."""
