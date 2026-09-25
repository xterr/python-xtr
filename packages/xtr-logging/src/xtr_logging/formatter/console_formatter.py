"""A short line for a terminal, optionally coloured by severity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_logging_contracts import Level

from .line_formatter import LineFormatter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_logging.log_record import LogRecord

__all__ = ["ConsoleFormatter"]

_DEFAULT_FORMAT: Final = "%datetime% %level_name% [%channel%] %message% %context% %extra%\n"
_DEFAULT_DATE_FORMAT: Final = "%H:%M:%S"
_LEVEL_TOKEN: Final = "%level_name%"  # noqa: S105 — a format token, not a secret
_RESET: Final = "\033[0m"

# ANSI colours graded by severity, so an error stands out in a scrolling
# terminal: dim for the quietest, yellow for the middle, red climbing to bold
# for anything that needs waking someone up.
_LEVEL_COLORS: Final[Mapping[Level, str]] = {
    Level.DEBUG: "\033[2m",
    Level.INFO: "\033[39m",
    Level.NOTICE: "\033[33m",
    Level.WARNING: "\033[33m",
    Level.ERROR: "\033[31m",
    Level.CRITICAL: "\033[31m",
    Level.ALERT: "\033[1;31m",
    Level.EMERGENCY: "\033[1;31m",
}


@final
class ConsoleFormatter(LineFormatter):
    """A compact line for a terminal, with the level name coloured on request.

    Shorter than :class:`LineFormatter`'s default — a wall-clock time rather
    than a full timestamp, the channel in brackets — because a console shows
    logs as they happen rather than for archiving, and an empty context or
    extra is left off by default for the same reason.

    With ``colors`` on, the level name is wrapped in an ANSI colour graded by
    severity; a
    :class:`~xtr_logging.handler.console_handler.ConsoleHandler` turns it on
    only when it is writing to a real terminal.
    """

    def __init__(  # noqa: PLR0913 — mirrors LineFormatter's keywords plus colours
        self,
        format: str | None = None,  # noqa: A002 — LineFormatter's name for it
        date_format: str | None = None,
        *,
        allow_inline_line_breaks: bool = False,
        ignore_empty_context_and_extra: bool = True,
        include_stacktraces: bool = False,
        colors: bool = False,
    ) -> None:
        """Configure the line, defaulting to the short console format.

        Args:
            format: The template; a short console line when omitted.
            date_format: A :meth:`~datetime.datetime.strftime` format;
                ``%H:%M:%S`` when omitted.
            allow_inline_line_breaks: Keep line breaks inside values.
            ignore_empty_context_and_extra: Leave an empty context or extra off
                the line rather than printing ``[]``; on by default here.
            include_stacktraces: Print an exception's traceback after it.
            colors: Wrap the level name in an ANSI colour graded by severity.
        """
        super().__init__(
            format if format is not None else _DEFAULT_FORMAT,
            date_format if date_format is not None else _DEFAULT_DATE_FORMAT,
            allow_inline_line_breaks=allow_inline_line_breaks,
            ignore_empty_context_and_extra=ignore_empty_context_and_extra,
            include_stacktraces=include_stacktraces,
        )
        self._colors: bool = colors

    @override
    def format(self, record: LogRecord, /) -> str:
        """Render ``record`` as a line, colouring the level name if colours are on."""
        line = super().format(record)
        if not self._colors or _LEVEL_TOKEN not in self._format:
            return line
        color = _LEVEL_COLORS[record.level]
        # The template puts the level name before the message, so the first
        # occurrence is the token, never a word that happens to sit in the text.
        return line.replace(record.level_name, f"{color}{record.level_name}{_RESET}", 1)
