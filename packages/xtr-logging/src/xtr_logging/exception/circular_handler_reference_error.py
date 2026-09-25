"""Handlers that nest each other in a loop."""

from __future__ import annotations

from xtr_logging_contracts import LoggingError

__all__ = ["CircularHandlerReferenceError"]


class CircularHandlerReferenceError(LoggingError):
    """Handlers nest each other in a loop, so none of them can be built first."""

    path: tuple[str, ...]

    def __init__(self, path: tuple[str, ...]) -> None:
        """Record the loop, starting and ending on the same handler."""
        self.path = path
        super().__init__(f"handlers nest each other in a loop: {' -> '.join(path)}")
