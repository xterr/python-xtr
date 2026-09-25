"""Capture is on while a handler sends records back into the standard library."""

from __future__ import annotations

from xtr_logging_contracts import LoggingError

__all__ = ["CaptureConflictError"]


class CaptureConflictError(LoggingError):
    """Capture is on while a ``stdlib`` handler sends records back into the standard library.

    While capture owns the standard library's output, a record handed to it
    arrives at the capture — which drops it, rather than send it round again —
    and nothing else is left to write it. The record would be lost, so the
    combination is refused.
    """

    handler: str

    def __init__(self, handler: str) -> None:
        """Record the handler that conflicts with capture."""
        self.handler = handler
        reason = "they would be dropped; remove the handler or the capture"
        super().__init__(f"handler {handler!r} sends records into the captured stdlib: {reason}")
