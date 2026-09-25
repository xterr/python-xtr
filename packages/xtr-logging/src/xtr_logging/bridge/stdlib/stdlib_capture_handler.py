"""A :mod:`logging` handler that feeds standard-library records into a channel.

Third-party code — uvicorn, SQLAlchemy, httpx, anything built on :mod:`logging`
— writes through the standard library, not through this one. Installed on those
loggers, this handler turns each of their records into a
:class:`~xtr_logging.log_record.LogRecord` on one of this library's channels,
keeping its time, its exception and whatever it attached through ``extra=``. A
record this library itself relayed out through
:class:`~xtr_logging.bridge.stdlib.stdlib_handler.StdlibHandler` is recognised
and dropped, so wiring both directions does not send a record round in circles.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_clock import DatePoint, local_timezone
from xtr_logging_contracts import EXCEPTION_KEY

from .level_mapping import from_stdlib, register_level_names
from .stdlib_handler import BRIDGED_MARKER

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_logging.logger import Logger

__all__ = ["StdlibCaptureHandler"]

# Everything a bare logging.LogRecord already carries; anything else on a record
# was put there by a caller through `extra=` and so belongs in the context.
# `message` and `asctime` are set by formatting rather than __init__, and
# `taskName` exists only on newer Pythons, so all three are named explicitly.
_STANDARD_ATTRIBUTES: Final[frozenset[str]] = frozenset(vars(logging.makeLogRecord({}))) | {
    "message",
    "asctime",
    "taskName",
}


@final
class StdlibCaptureHandler(logging.Handler):
    """Turns the standard library's records into records on a channel.

    The channel is chosen per record: the ``routes`` entry for the most
    specific standard logger name that matches — ``httpx`` catches
    ``httpx._client`` too — or, with ``channel_from_name``, one named after the
    standard logger the record came from, so ``sqlalchemy.engine`` and
    ``uvicorn.access`` stay apart the way they were; otherwise the channel this
    handler was built for. Per-name channels are made once and reused.
    """

    def __init__(
        self,
        logger: Logger,
        *,
        routes: Mapping[str, Logger] | None = None,
        channel_from_name: bool = False,
        level: int = logging.NOTSET,
    ) -> None:
        """Capture into ``logger``.

        Args:
            logger: The channel captured records are added to, or the channel
                whose handlers and processors the per-name channels share.
            routes: The channel for records from a standard logger and its
                children, by standard logger name; the longest match wins.
            channel_from_name: Route a record no route matches to a channel
                named after the standard logger it came from, rather than to
                ``logger`` itself.
            level: The standard-library level below which records are dropped
                before this handler sees them; the loggers it is installed on
                have their own levels too.
        """
        super().__init__(level)
        register_level_names()
        self._logger: Logger = logger
        self._channel_from_name: bool = channel_from_name
        # Longest name first, so the first match is the most specific.
        self._routes: tuple[tuple[str, Logger], ...] = tuple(
            sorted((routes or {}).items(), key=lambda route: -len(route[0])),
        )
        self._by_name: dict[str, Logger] = {}

    @override
    def emit(self, record: logging.LogRecord) -> None:
        """Add ``record`` to a channel, unless this library sent it out.

        Keeps :class:`logging.Handler`'s contract of never letting an error
        escape: anything that goes wrong is reported through
        :meth:`logging.Handler.handleError`, which respects
        :data:`logging.raiseExceptions`, rather than propagating to the code
        that happened to be logging.
        """
        marker: object = getattr(record, BRIDGED_MARKER, False)
        if marker:
            return
        try:
            self._capture(record)
        except RecursionError:  # pragma: no cover - stdlib re-raises to surface a stack overflow
            raise
        except Exception:  # noqa: BLE001 - Handler.emit reports via handleError, never propagates
            self.handleError(record)

    def _capture(self, record: logging.LogRecord) -> None:
        attributes: dict[str, object] = vars(record)
        context: dict[str, object] = {
            name: value for name, value in attributes.items() if name not in _STANDARD_ATTRIBUTES
        }
        exc_info = record.exc_info
        exception = exc_info[1] if exc_info is not None else None
        if isinstance(exception, BaseException):
            context[EXCEPTION_KEY] = exception
        when = DatePoint.fromtimestamp(record.created, local_timezone())
        _ = self._target_for(record.name).add_record(
            from_stdlib(record.levelno),
            record.getMessage(),
            context,
            datetime=when,
        )

    def _target_for(self, name: str) -> Logger:
        for prefix, routed in self._routes:
            if name == prefix or name.startswith(f"{prefix}."):
                return routed
        if not self._channel_from_name:
            return self._logger
        cached = self._by_name.get(name)
        if cached is None:
            cached = self._logger.with_name(name)
            self._by_name[name] = cached
        return cached
