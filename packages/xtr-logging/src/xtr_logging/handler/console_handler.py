"""A handler for a command's console, whose level follows how verbose it was asked to be."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_logging.formatter.console_formatter import ConsoleFormatter
from xtr_logging.level import Level
from xtr_logging.verbosity import Verbosity

from .abstract_processing_handler import AbstractProcessingHandler

if TYPE_CHECKING:
    from collections.abc import Mapping
    from typing import TextIO

    from xtr_logging.formatter.formatter_interface import FormatterInterface
    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import LogRecord

__all__ = ["ConsoleHandler"]

# The verbosity a command runs at decides how low a level it prints: a quiet
# command shows only errors, a fully verbose one shows everything.
_DEFAULT_VERBOSITY_LEVELS: Final[Mapping[Verbosity, Level]] = {
    Verbosity.QUIET: Level.ERROR,
    Verbosity.NORMAL: Level.WARNING,
    Verbosity.VERBOSE: Level.NOTICE,
    Verbosity.VERY_VERBOSE: Level.INFO,
    Verbosity.DEBUG: Level.DEBUG,
}


@final
class ConsoleHandler(AbstractProcessingHandler):
    """Writes to a console, at a level set by how verbose the command is.

    A console command chooses its verbosity from its ``-v`` flags; this
    handler turns that into a log level, so ``-vv`` surfaces info and a quiet
    run shows only errors. The level is recomputed whenever the verbosity is
    set, which a command does once it has parsed its input.

    The stream defaults to standard error, resolved at write time so a test
    that swaps ``sys.stderr`` is written to, and colours are on only when that
    stream is a real terminal.
    """

    def __init__(
        self,
        stream: TextIO | None = None,
        verbosity: Verbosity = Verbosity.NORMAL,
        verbosity_levels: Mapping[Verbosity, LevelLike] | None = None,
        bubble: bool = True,
    ) -> None:
        """Write to ``stream`` at the level ``verbosity`` maps to.

        Args:
            stream: Where to write; standard error, resolved at write time,
                when omitted.
            verbosity: The verbosity the command is running at.
            verbosity_levels: Overrides for the verbosity-to-level map; the
                keys given replace the defaults, the rest stand.
            bubble: Let a handled record reach later handlers.
        """
        self._levels: dict[Verbosity, Level] = dict(_DEFAULT_VERBOSITY_LEVELS)
        if verbosity_levels is not None:
            for key, value in verbosity_levels.items():
                self._levels[key] = Level.parse(value)
        self._verbosity: Verbosity = verbosity
        super().__init__(self._levels[verbosity], bubble)
        self._stream: TextIO | None = stream

    @property
    def verbosity(self) -> Verbosity:
        """The verbosity the handler is printing at."""
        return self._verbosity

    def set_verbosity(self, verbosity: Verbosity) -> None:
        """Print at the level ``verbosity`` maps to from now on."""
        self._verbosity = verbosity
        self.set_level(self._levels[verbosity])

    @override
    def write(self, record: LogRecord, formatted: str) -> None:
        """Write ``formatted`` to the stream, or to standard error."""
        stream = self._resolve_stream()
        _ = stream.write(formatted)
        stream.flush()

    @override
    def default_formatter(self) -> FormatterInterface:
        """A short console line, coloured when writing to a real terminal."""
        return ConsoleFormatter(colors=self._resolve_stream().isatty())

    def _resolve_stream(self) -> TextIO:
        return self._stream if self._stream is not None else sys.stderr
