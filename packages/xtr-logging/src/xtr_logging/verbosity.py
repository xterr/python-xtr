"""Console verbosity levels, so a handler can follow the ``-v`` flags."""

from __future__ import annotations

from enum import IntEnum
from typing import Final

__all__ = ["Verbosity"]

_VERBOSE_AT: Final = 1
_VERY_VERBOSE_AT: Final = 2
_DEBUG_AT: Final = 3


class Verbosity(IntEnum):
    """How much a console command was told to say.

    A command run with more ``-v`` flags shows more, and these are the
    thresholds a :class:`~xtr_logging.handler.console_handler.ConsoleHandler`
    maps to log levels. The values are powers of two, leaving room for a level
    in between.
    """

    SILENT = 8
    QUIET = 16
    NORMAL = 32
    VERBOSE = 64
    VERY_VERBOSE = 128
    DEBUG = 256

    @classmethod
    def from_count(cls, verbose: int, *, quiet: bool = False, silent: bool = False) -> Verbosity:
        """Read the verbosity a count of ``-v`` flags asks for.

        ``--silent`` wins over ``-q``, which silences a command however often
        ``-v`` was also given.
        """
        if silent:
            return cls.SILENT
        if quiet:
            return cls.QUIET
        if verbose >= _DEBUG_AT:
            return cls.DEBUG
        if verbose == _VERY_VERBOSE_AT:
            return cls.VERY_VERBOSE
        if verbose == _VERBOSE_AT:
            return cls.VERBOSE
        return cls.NORMAL
