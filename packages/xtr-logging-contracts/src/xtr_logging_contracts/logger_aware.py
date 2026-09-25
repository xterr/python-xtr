"""A mixin giving a class a logger that is never missing."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override

from .logger_aware_interface import LoggerAwareInterface
from .null_logger import NullLogger

if TYPE_CHECKING:
    from .logger_interface import LoggerInterface

__all__ = ["LoggerAware"]


class LoggerAware(LoggerAwareInterface):
    """Holds a logger, defaulting to a :class:`NullLogger`.

    Code in the class logs through :attr:`logger` without checking whether one
    was ever set.
    """

    _default: ClassVar[LoggerInterface] = NullLogger()
    _logger: LoggerInterface | None = None

    @property
    def logger(self) -> LoggerInterface:
        """The logger set last, or one that discards everything."""
        return self._logger if self._logger is not None else self._default

    @override
    def set_logger(self, logger: LoggerInterface, /) -> None:
        """Log through ``logger`` from now on."""
        self._logger = logger
