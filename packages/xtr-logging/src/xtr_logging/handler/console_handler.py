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
    from typing import IO

    from xtr_logging.formatter.formatter_interface import FormatterInterface
    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import LogRecord

__all__ = ["ConsoleHandler"]

# The verbosity a command runs at decides how low a level it prints: a quiet
# command shows only errors, a fully verbose one shows everything. A silent
# one shows nothing, which no level can say; the handler refuses every record.
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
    handler turns that into a log level, so ``-vv`` surfaces info, a quiet
    run shows only errors and a silent one nothing at all. The level is
    recomputed whenever the verbosity is set, which a command does once it has
    parsed its input.

    The stream defaults to standard error, resolved at write time so a test
    that swaps ``sys.stderr`` is written to, and colours are on only when that
    stream is a real terminal. :meth:`set_stream` moves both, as a console
    application does to follow the output of the command it runs.
    """

    def __init__(
        self,
        stream: IO[str] | None = None,
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
                :attr:`Verbosity.SILENT` prints nothing, whatever it maps to.
            bubble: Let a handled record reach later handlers.
        """
        self._levels: dict[Verbosity, Level] = dict(_DEFAULT_VERBOSITY_LEVELS)
        if verbosity_levels is not None:
            for key, value in verbosity_levels.items():
                self._levels[key] = Level.parse(value)
        self._verbosity: Verbosity = verbosity
        super().__init__(self._level_for(verbosity), bubble)
        self._stream: IO[str] | None = stream
        self._colors: bool | None = None
        self._built_formatter: FormatterInterface | None = None

    @property
    def verbosity(self) -> Verbosity:
        """The verbosity the handler is printing at."""
        return self._verbosity

    def set_verbosity(self, verbosity: Verbosity) -> None:
        """Print at the level ``verbosity`` maps to from now on."""
        self._verbosity = verbosity
        self.set_level(self._level_for(verbosity))

    def set_stream(self, stream: IO[str] | None, *, colors: bool | None = None) -> None:
        """Write to ``stream`` from now on.

        Args:
            stream: Where to write; standard error, resolved at write time,
                when ``None``.
            colors: Colour the level names, or not; ``None`` colours them only
                on a real terminal. A formatter set by hand is kept as it is.
        """
        self._stream = stream
        self._colors = colors
        if self._formatter is self._built_formatter:
            self._formatter = None

    @override
    def is_handling(self, record: LogRecord, /) -> bool:
        """Whether ``record`` is at the level, and the command is not silent."""
        return self._verbosity is not Verbosity.SILENT and super().is_handling(record)

    @override
    def write(self, record: LogRecord, formatted: str) -> None:
        """Write ``formatted`` to the stream, or to standard error."""
        stream = self._resolve_stream()
        _ = stream.write(formatted)
        stream.flush()

    @override
    def default_formatter(self) -> FormatterInterface:
        """A short console line, coloured as :meth:`set_stream` said, or on a real terminal."""
        colors = self._colors if self._colors is not None else self._resolve_stream().isatty()
        self._built_formatter = ConsoleFormatter(colors=colors)
        return self._built_formatter

    def _level_for(self, verbosity: Verbosity) -> Level:
        """Return the level ``verbosity`` maps to; the highest for one that prints nothing."""
        return self._levels.get(verbosity, Level.EMERGENCY)

    def _resolve_stream(self) -> IO[str]:
        return self._stream if self._stream is not None else sys.stderr
