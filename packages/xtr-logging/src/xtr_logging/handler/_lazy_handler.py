"""The handler a wrapper forwards to, built the first time a record needs it."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from xtr_service_contracts import ResetInterface

from .handler_interface import HandlerInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_logging.log_record import LogRecord

__all__ = ["LazyHandler"]


class LazyHandler:
    """Holds a wrapped handler, or the factory ``factory(record, wrapper)`` that builds it.

    The factory runs the first time a record needs the handler, and never
    otherwise: closing or resetting a wrapper whose handler was never built
    leaves it unbuilt, so an expensive handler costs nothing to a unit of
    work that stayed quiet.
    """

    _wrapped: HandlerInterface | None = None
    _factory: Callable[..., HandlerInterface] | None = None

    def _wrap(self, handler: HandlerInterface | Callable[..., HandlerInterface]) -> None:
        """Forward to ``handler``, or to what it builds when it is a factory."""
        if isinstance(handler, HandlerInterface):
            self._wrapped, self._factory = handler, None
        else:
            self._wrapped, self._factory = None, handler

    def _resolve_handler(self, record: LogRecord | None = None) -> HandlerInterface:
        """Return the wrapped handler, building it now if it is not built yet."""
        wrapped = self._wrapped
        if wrapped is None:
            wrapped = cast("Callable[..., HandlerInterface]", self._factory)(record, self)
            self._wrapped, self._factory = wrapped, None
        return wrapped

    def _close_handler(self) -> None:
        """Close the wrapped handler, if it was ever built."""
        if self._wrapped is not None:
            self._wrapped.close()

    def _reset_handler(self) -> None:
        """Reset the wrapped handler, if it was ever built and holds state."""
        if isinstance(self._wrapped, ResetInterface):
            self._wrapped.reset()
