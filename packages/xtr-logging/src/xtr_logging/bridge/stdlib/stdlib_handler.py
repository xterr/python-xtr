"""A handler that hands records to the standard library's :mod:`logging`.

For an application that already has :mod:`logging` configured — a file, a
syslog socket, whatever — and wants this library's channels to feed into it
rather than replace it. The record keeps its original time, and is marked so
that :class:`~xtr_logging.bridge.stdlib.stdlib_capture_handler.StdlibCaptureHandler`
can tell it came from here and not carry it back, were both directions wired
at once.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_logging.handler.abstract_handler import AbstractHandler
from xtr_logging.level import Level

from .level_mapping import register_level_names, to_stdlib

if TYPE_CHECKING:
    from types import TracebackType

    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import LogRecord

__all__ = ["BRIDGED_MARKER", "CHANNEL_ATTR", "CONTEXT_ATTR", "EXTRA_ATTR", "StdlibHandler"]

#: Set on every stdlib record this handler makes, so a capture handler on the
#: other side knows the record is already ours and refuses to loop it back.
BRIDGED_MARKER: Final = "xtr_logging_bridged"

#: The attribute a bridged stdlib record carries its channel under. Prefixed so
#: it cannot collide with a standard :class:`logging.LogRecord` attribute, which
#: :meth:`logging.Logger.makeRecord` refuses to let ``extra`` overwrite.
CHANNEL_ATTR: Final = "xtr_channel"

#: The attribute a bridged stdlib record carries its context mapping under.
CONTEXT_ATTR: Final = "xtr_context"

#: The attribute a bridged stdlib record carries its processor extra under.
EXTRA_ATTR: Final = "xtr_extra"


@final
class StdlibHandler(AbstractHandler):
    """Forwards each record to a :class:`logging.Logger`, time and all.

    A record is offered to the standard library only when that logger is
    enabled for the matching level, so :mod:`logging`'s own configuration has
    the final say on what it keeps — this handler decides what to relay, not
    what to write.
    """

    def __init__(
        self,
        logger: logging.Logger | str,
        level: LevelLike = Level.DEBUG,
        bubble: bool = True,
    ) -> None:
        """Relay records at ``level`` or above to ``logger``.

        Args:
            logger: A :class:`logging.Logger`, or the name of one to fetch.
            level: The least severe level to relay.
            bubble: Whether a relayed record still reaches later handlers.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        super().__init__(level, bubble)
        register_level_names()
        self._logger: logging.Logger = (
            logger if isinstance(logger, logging.Logger) else logging.getLogger(logger)
        )

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Relay ``record`` to the standard library if both sides want it.

        Returns ``False`` — letting the record bubble — when this handler's
        level or the standard logger's own level turns it away, since nothing
        was written; otherwise returns whether ``bubble`` is off.
        """
        if not self.is_handling(record):
            return False
        levelno = to_stdlib(record.level)
        if not self._logger.isEnabledFor(levelno):
            return False
        stdlib_record = self._logger.makeRecord(
            self._logger.name,
            levelno,
            "",
            0,
            record.message,
            (),
            _exc_info_from(record.exception),
            None,
            {
                CHANNEL_ATTR: record.channel,
                CONTEXT_ATTR: dict(record.context),
                EXTRA_ATTR: dict(record.extra),
                BRIDGED_MARKER: True,
            },
        )
        # Keep the moment the record was made, not the moment it was relayed.
        stdlib_record.created = record.datetime.timestamp()
        stdlib_record.msecs = record.datetime.microsecond / 1000
        self._logger.handle(stdlib_record)
        return not self.bubble


def _exc_info_from(
    exception: BaseException | None,
) -> tuple[type[BaseException], BaseException, TracebackType | None] | None:
    if exception is None:
        return None
    return type(exception), exception, exception.__traceback__
