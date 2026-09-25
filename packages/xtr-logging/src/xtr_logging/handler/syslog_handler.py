"""Records to a syslog daemon, sent through the standard library's transport."""

from __future__ import annotations

import logging
import socket
from logging.handlers import SysLogHandler as _StdlibSysLogHandler
from typing import TYPE_CHECKING, ClassVar, Final, final

from typing_extensions import override
from xtr_logging_contracts import Level

from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.formatter.line_formatter import LineFormatter

from .abstract_processing_handler import AbstractProcessingHandler

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_logging_contracts import LevelLike

    from xtr_logging.formatter.formatter_interface import FormatterInterface
    from xtr_logging.log_record import LogRecord

__all__ = ["SyslogHandler"]

_SYSLOG_FORMAT: Final = "%channel%.%level_name%: %message% %context% %extra%"

# Each level's name maps to the syslog severity word the stdlib handler turns
# into an RFC 5424 number, covering the three levels its default map omits
# (notice, alert, emergency) as well as the five it already knows.
_PRIORITY_MAP: Final[Mapping[str, str]] = {
    Level.DEBUG.name: "debug",
    Level.INFO.name: "info",
    Level.NOTICE.name: "notice",
    Level.WARNING.name: "warning",
    Level.ERROR.name: "error",
    Level.CRITICAL.name: "critical",
    Level.ALERT.name: "alert",
    Level.EMERGENCY.name: "emerg",
}


@final
class _RaisingSysLogHandler(_StdlibSysLogHandler):
    """A stdlib syslog handler that lets a send failure surface.

    The standard library swallows an emit error into ``handleError`` and logs
    it to stderr; this library propagates handler failures instead, so a lost
    datagram is not hidden behind a green log call. It also carries the full
    eight-level severity map, which the stdlib reads off the handler.
    """

    priority_map: ClassVar[dict[str, str]] = dict(_PRIORITY_MAP)

    @override
    def handleError(self, record: logging.LogRecord) -> None:
        raise  # noqa: PLE0704 — re-raise the emit failure emit() is handling, rather than swallow it


@final
class SyslogHandler(AbstractProcessingHandler):
    """Sends each record to a syslog daemon with its RFC 5424 severity.

    The transport is the standard library's ``SysLogHandler``, opened on the
    first record and closed by :meth:`close`. Each record is handed to it as a
    synthetic stdlib record whose level name maps, through
    :attr:`priority_map`, to the syslog severity — so the datagram's priority
    is ``facility * 8 + severity`` with the severity this library assigns.
    """

    priority_map: ClassVar[Mapping[str, str]] = _PRIORITY_MAP
    """Level name to syslog severity word, for every one of the eight levels."""

    def __init__(  # noqa: PLR0913 — everything past `bubble` is keyword-only
        self,
        ident: str = "python",
        facility: int | str = "user",
        level: LevelLike = Level.DEBUG,
        bubble: bool = True,
        *,
        address: str | tuple[str, int] = ("localhost", 514),
        socktype: int | None = None,
    ) -> None:
        """Send records to the syslog daemon at ``address`` under ``facility``.

        Args:
            ident: Prefixed to every line as ``ident: ``, naming the sender.
            facility: A syslog facility, by name (``"user"``, ``"local0"``) or
                by its integer.
            level: Handle records at this level or above.
            bubble: Let a handled record reach later handlers.
            address: A ``(host, port)`` pair, or the path of a local socket.
            socktype: A ``socket`` type; the stdlib default (UDP) when omitted.

        Raises:
            InvalidOptionError: If ``facility`` names no known facility.
            InvalidLevelError: If ``level`` names no level.
        """
        super().__init__(level, bubble)
        self._ident: str = ident
        self._facility: int = _resolve_facility(facility)
        self._address: str | tuple[str, int] = address
        self._socktype: int | None = socktype
        self._transport: _RaisingSysLogHandler | None = None

    @override
    def write(self, record: LogRecord, formatted: str) -> None:
        """Hand ``formatted`` to the transport with the record's severity."""
        transport = self._transport if self._transport is not None else self._open_transport()
        entry = logging.LogRecord(
            record.channel,
            logging.INFO,
            "",
            0,
            formatted,
            None,
            None,
        )
        entry.levelname = record.level.name
        transport.emit(entry)

    @override
    def close(self) -> None:
        """Close the transport; the next record opens a fresh one."""
        if self._transport is not None:
            self._transport.close()
            self._transport = None

    @override
    def default_formatter(self) -> FormatterInterface:
        """A line without a datetime, since the syslog daemon stamps its own."""
        return LineFormatter(_SYSLOG_FORMAT)

    def _open_transport(self) -> _RaisingSysLogHandler:
        transport = (
            _RaisingSysLogHandler(self._address, self._facility)
            if self._socktype is None
            else _RaisingSysLogHandler(
                self._address, self._facility, socket.SocketKind(self._socktype)
            )
        )
        transport.ident = f"{self._ident}: "
        self._transport = transport
        return transport


def _resolve_facility(facility: int | str) -> int:
    if isinstance(facility, int):
        return facility
    resolved = _StdlibSysLogHandler.facility_names.get(facility)
    if resolved is None:
        known = ", ".join(sorted(_StdlibSysLogHandler.facility_names))
        raise InvalidOptionError("facility", facility, f"names no syslog facility; known: {known}")
    return resolved
