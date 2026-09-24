"""Something that can be handed a logger after it is built."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from .logger_interface import LoggerInterface

__all__ = ["LoggerAwareInterface"]


@runtime_checkable
class LoggerAwareInterface(Protocol):
    """Accepts a logger through a setter.

    Prefer a constructor argument. This exists for objects a framework builds
    for you, where the constructor is not yours to extend.
    """

    def set_logger(self, logger: LoggerInterface, /) -> None:
        """Log through ``logger`` from now on."""
        ...
