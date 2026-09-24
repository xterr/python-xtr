"""A handler was named that the configuration does not define."""

from __future__ import annotations

from .logging_error import LoggingError

__all__ = ["UnknownHandlerError"]


class UnknownHandlerError(LoggingError):
    """A handler was named that the configuration does not define.

    Raised as the configuration is made — for a wrapper whose nested handler
    or member is missing, or a processor targeting one — and by a factory
    asked for a handler by a name it never built.
    """

    name: str
    referenced_by: str
    known: tuple[str, ...]

    def __init__(self, name: str, referenced_by: str, known: tuple[str, ...]) -> None:
        """Record the missing name, who asked for it, and what is defined."""
        self.name = name
        self.referenced_by = referenced_by
        self.known = known
        defined = ", ".join(known) or "<none>"
        super().__init__(
            f"{referenced_by} names handler {name!r}, which is not defined; defined: {defined}"
        )
