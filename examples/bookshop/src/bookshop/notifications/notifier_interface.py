"""What sends a message to someone."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["NotifierInterface"]


@runtime_checkable
class NotifierInterface(Protocol):
    """Delivers ``message`` to ``recipient`` and says how."""

    def notify(self, recipient: str, message: str, /) -> str:
        """Deliver, and return a short description of the delivery."""
        ...
