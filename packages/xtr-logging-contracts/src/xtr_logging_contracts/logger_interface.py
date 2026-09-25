"""The logging surface code writes through."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .context import Context
    from .level import LevelLike

__all__ = ["LoggerInterface"]


@runtime_checkable
class LoggerInterface(Protocol):
    """Writes messages at one of eight severities, with structured context.

    The only type code that logs should depend on. Whatever implements it —
    a channel of ``xtr-logging``'s ``Logger``, a
    :class:`~xtr_logging_contracts.null_logger.NullLogger`, an adapter over a
    standard library logger — can be swapped without touching a call site.

    The rules:

    - ``message`` may hold ``{key}`` placeholders naming entries of
      ``context``. The logger does not substitute them; something later in the
      pipeline does — ``xtr-logging``'s ``PlaceholderProcessor`` — so a handler
      may still see the template and the values apart.
    - An exception to report goes under ``context["exception"]``.
    - Context is data, never code: an implementation must not fail because of
      what it holds.

    ``message`` is positional-only, so an implementation may name it freely;
    ``context`` may also be passed by keyword.
    """

    def emergency(self, message: str, /, context: Context | None = None) -> None:
        """The system is unusable."""
        ...

    def alert(self, message: str, /, context: Context | None = None) -> None:
        """Action must be taken immediately — the whole site is down, say."""
        ...

    def critical(self, message: str, /, context: Context | None = None) -> None:
        """A critical condition, such as an unavailable component."""
        ...

    def error(self, message: str, /, context: Context | None = None) -> None:
        """A runtime error that needs no immediate action but must be seen."""
        ...

    def warning(self, message: str, /, context: Context | None = None) -> None:
        """Something exceptional that is not an error, like a deprecated call."""
        ...

    def notice(self, message: str, /, context: Context | None = None) -> None:
        """A normal but significant event."""
        ...

    def info(self, message: str, /, context: Context | None = None) -> None:
        """An interesting event, such as a user logging in."""
        ...

    def debug(self, message: str, /, context: Context | None = None) -> None:
        """Detailed information for debugging."""
        ...

    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        """Log at ``level``, given in any form :meth:`Level.parse` accepts.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        ...
