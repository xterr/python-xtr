"""A :class:`LoggerInterface` whose backend is a plain :class:`logging.Logger`.

The mirror of :class:`~xtr_logging.bridge.stdlib.stdlib_handler.StdlibHandler`:
that one lets this library's channels feed into :mod:`logging`; this one lets
code depend on :class:`~xtr_logging.logger_interface.LoggerInterface` while
:mod:`logging` stays the backend that actually writes. A call is translated
into the level, exception and caller information :mod:`logging` expects, so its
handlers and formatters see exactly what they would from a native call.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_logging_contracts import EXCEPTION_KEY, AbstractLogger, Level

from .level_mapping import register_level_names, to_stdlib
from .stdlib_handler import CONTEXT_ATTR

if TYPE_CHECKING:
    from xtr_logging_contracts import Context, LevelLike

__all__ = ["StdlibLogger"]

# A severity call travels caller -> AbstractLogger.info -> StdlibLogger.log ->
# logging.Logger.log before logging looks for who logged. Three frames stand
# between that search and the caller, so telling logging to skip them makes its
# %(funcName)s and %(lineno)d name the caller rather than this adapter.
_STACKLEVEL: Final = 3


@final
class StdlibLogger(AbstractLogger):
    """Logs through a :class:`logging.Logger` behind this library's interface.

    Context is carried on the record under ``xtr_context`` for a formatter that
    knows to read it, kept together the way this library keeps it rather than
    scattered across attributes. An exception under ``context["exception"]``
    becomes the record's ``exc_info``, so a traceback is rendered as usual.
    """

    def __init__(self, logger: logging.Logger | str) -> None:
        """Log through ``logger``, or through the :class:`logging.Logger` so named."""
        register_level_names()
        self._logger: logging.Logger = (
            logger if isinstance(logger, logging.Logger) else logging.getLogger(logger)
        )

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        """Log ``message`` at ``level`` through the standard library.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        values: Context = context if context is not None else {}
        reported = values.get(EXCEPTION_KEY)
        exception = reported if isinstance(reported, BaseException) else None
        self._logger.log(
            to_stdlib(Level.parse(level)),
            message,
            exc_info=exception,
            extra={CONTEXT_ATTR: dict(values)},
            stacklevel=_STACKLEVEL,
        )
