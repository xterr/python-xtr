"""The base of every ordering error."""

from __future__ import annotations

__all__ = ["OrderError"]


class OrderError(Exception):
    """Every ordering error derives from this one."""
