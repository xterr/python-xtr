"""Taking over the standard library's output, so every record is written once.

Capturing is not adding a handler. A handler added next to the ones already
there — a root ``StreamHandler`` from :func:`logging.basicConfig`, a handler a
library attached to its own logger — leaves them printing too, and every
record comes out twice: once through the standard library, once through a
channel. So a capture *replaces* the standard library's output instead. While
it is installed the one capture handler, on the root logger, is the only
handler anywhere in the tree; everything else it moved aside comes back when
it is released.

That has to hold for handlers attached later, too: the standard library calls
a logger's own handlers before its parents', so one attached to a library's
logger after the capture started would print a record before the capture ever
saw it. While a capture is installed, :meth:`logging.Logger.addHandler` and
:meth:`logging.Logger.removeHandler` are therefore routed through it — a
handler attached anywhere is held aside, to be attached for real when the
capture is released, and the capture's own handler cannot be taken off the
root. Both methods are the standard library's own again the moment the last
capture is released.

A record whose logger has no handler to reach — one reconfigured not to
propagate, its handlers held aside — would fall through to
:data:`logging.lastResort` and be printed raw to standard error. While
installed, the capture handler *is* the last resort, so that record is
captured instead.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, final

from xtr_logging_contracts import Level

from .level_mapping import register_level_names, to_stdlib
from .stdlib_capture_handler import StdlibCaptureHandler

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import TracebackType
    from typing import Self

    from xtr_logging_contracts import LevelLike

    from xtr_logging.logger import Logger

__all__ = ["StdlibCapture"]

_ADD_HANDLER: Final = logging.Logger.addHandler
_REMOVE_HANDLER: Final = logging.Logger.removeHandler

# Installed captures, most recent last. Only the most recent owns the output.
_captures: list[StdlibCapture] = []


# Named as the standard library names them: these stand in for its methods.
def _add_handler(self: logging.Logger, hdlr: logging.Handler) -> None:
    """``Logger.addHandler`` while a capture is installed: hold the handler aside."""
    _captures[-1].hold(self, hdlr)


def _remove_handler(self: logging.Logger, hdlr: logging.Handler) -> None:
    """``Logger.removeHandler`` while a capture is installed: forget a held handler."""
    _captures[-1].drop(self, hdlr)


def _intercept(active: bool) -> None:
    """Route ``addHandler`` and ``removeHandler`` through the capture, or give them back."""
    logging.Logger.addHandler = _add_handler if active else _ADD_HANDLER
    logging.Logger.removeHandler = _remove_handler if active else _REMOVE_HANDLER


@dataclass(slots=True)
class _Saved:
    """How a standard logger was set up before the capture changed it."""

    handlers: list[logging.Handler]
    level: int
    propagate: bool
    disabled: bool


@final
class StdlibCapture:
    """Routes every standard-library record into channels, and nowhere else.

    On :meth:`install`:

    - every existing standard logger loses its handlers, is re-enabled, and
      propagates again, so each record reaches the root;
    - the root loses its handlers and gets the one capture handler, at
      ``level``;
    - each logger named in ``levels`` is set to its own level.

    Every record the capture handler sees is also checked against the chain of
    loggers it came through. A handler some code attached after installation
    Handlers attached while it is installed — through ``addHandler``, as
    :func:`logging.basicConfig` and :func:`logging.config.dictConfig` attach
    them — are held aside rather than attached. A logger reconfigured not to
    propagate is made to again by its first record. And as a last line, every
    record the capture handler sees is checked against the loggers it came
    through, for anything put straight into a ``handlers`` list.

    Captures nest: the most recent one owns the output until it is released.

    :meth:`release` puts back every handler, level and flag it changed.
    """

    __slots__ = ("_handler", "_last_resort", "_levels", "_root_level", "_saved")

    def __init__(
        self,
        logger: Logger,
        *,
        level: LevelLike = Level.WARNING,
        levels: Mapping[str, LevelLike] | None = None,
        routes: Mapping[str, Logger] | None = None,
    ) -> None:
        """Capture into ``logger``, or into the channel ``routes`` gives a logger.

        Args:
            logger: The channel records arrive on unless a route says otherwise.
            level: The root's level: the threshold for every standard logger
                that sets none of its own.
            levels: A level per standard logger name, for loggers that should
                say more or less than the root lets through.
            routes: A channel per standard logger name; a logger's children
                follow it, and the most specific name wins.

        Raises:
            InvalidLevelError: If a level names no level.
        """
        self._handler: StdlibCaptureHandler = StdlibCaptureHandler(logger, routes=routes)
        self._handler.addFilter(self._take_over_origin)
        self._root_level: int = to_stdlib(Level.parse(level))
        self._levels: dict[str, int] = {
            name: to_stdlib(Level.parse(value)) for name, value in (levels or {}).items()
        }
        self._saved: dict[logging.Logger, _Saved] = {}
        self._last_resort: logging.Handler | None = None

    @property
    def installed(self) -> bool:
        """Whether the capture currently owns the standard library's output."""
        return bool(self._saved)

    def install(self) -> None:
        """Take over every standard logger. Installing twice changes nothing."""
        if self.installed:
            return
        register_level_names()
        if not _captures:
            _intercept(active=True)
        _captures.append(self)
        root = logging.getLogger()
        existing = [
            candidate
            for candidate in logging.Logger.manager.loggerDict.values()
            if isinstance(candidate, logging.Logger)
        ]
        for candidate in (*existing, root):
            self._take_over(candidate)
        _ADD_HANDLER(root, self._handler)
        root.setLevel(self._root_level)
        self._last_resort = logging.lastResort
        logging.lastResort = self._handler
        for name, level in self._levels.items():
            named = logging.getLogger(name)
            self._take_over(named)
            named.setLevel(level)

    def release(self) -> None:
        """Give every standard logger back exactly as it was found.

        Handlers attached while the capture was installed are attached now.
        """
        if not self.installed:
            return
        _captures.remove(self)
        if not _captures:
            _intercept(active=False)
        _REMOVE_HANDLER(logging.getLogger(), self._handler)
        logging.lastResort = self._last_resort
        for taken, saved in self._saved.items():
            taken.handlers = list(saved.handlers)
            taken.setLevel(saved.level)
            taken.propagate = saved.propagate
            taken.disabled = saved.disabled
        self._saved.clear()

    def __enter__(self) -> Self:
        """Install for the ``with`` block."""
        self.install()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release, whatever happened in the block."""
        self.release()

    def hold(self, logger: logging.Logger, handler: logging.Handler) -> None:
        """Keep ``handler`` for ``logger`` until release, instead of attaching it."""
        if handler is self._handler:
            _ADD_HANDLER(logger, handler)
            return
        self._take_over(logger)
        held = self._saved[logger].handlers
        if handler not in held:
            held.append(handler)

    def drop(self, logger: logging.Logger, handler: logging.Handler) -> None:
        """Forget a held ``handler``; the capture's own handler stays where it is."""
        if handler is self._handler:
            return
        _REMOVE_HANDLER(logger, handler)
        saved = self._saved.get(logger)
        if saved is not None and handler in saved.handlers:
            saved.handlers.remove(handler)

    def _take_over(self, taken: logging.Logger) -> None:
        """Move ``taken``'s handlers aside and make it propagate, remembering how it was."""
        saved = self._saved.get(taken)
        if saved is None:
            saved = _Saved([], taken.level, taken.propagate, taken.disabled)
            self._saved[taken] = saved
        foreign = [handler for handler in taken.handlers if handler is not self._handler]
        saved.handlers.extend(foreign)
        # Assigned rather than mutated: the standard library may be iterating
        # the old list for the record being handled right now.
        taken.handlers = [handler for handler in taken.handlers if handler is self._handler]
        taken.propagate = True
        taken.disabled = False

    def _take_over_origin(self, record: logging.LogRecord) -> bool:
        """Move aside anything put on the record's way up since installation."""
        current: logging.Logger | None = logging.getLogger(record.name)
        while current is not None:
            foreign = any(handler is not self._handler for handler in current.handlers)
            if foreign or not current.propagate or current.disabled:
                self._take_over(current)
            current = current.parent
        return True
