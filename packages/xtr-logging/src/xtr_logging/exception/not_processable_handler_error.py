"""A processor targets a handler that runs no processors."""

from __future__ import annotations

from .logging_error import LoggingError

__all__ = ["NotProcessableHandlerError"]


class NotProcessableHandlerError(LoggingError):
    """A processor targets a handler that runs no processors of its own."""

    handler: str

    def __init__(self, handler: str) -> None:
        """Record the handler that cannot take a processor."""
        self.handler = handler
        super().__init__(f"handler {handler!r} runs no processors, so none can target it")
