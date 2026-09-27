"""A handler that runs its own processors, formats, and writes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_logging_contracts import Level

from xtr_logging.formatter.line_formatter import LineFormatter

from ._processor_stack import ProcessorStack
from .abstract_handler import AbstractHandler
from .formattable_handler_interface import FormattableHandlerInterface

if TYPE_CHECKING:
    from xtr_logging_contracts import LevelLike

    from xtr_logging.formatter.formatter_interface import FormatterInterface
    from xtr_logging.log_record import LogRecord

__all__ = ["AbstractProcessingHandler"]


class AbstractProcessingHandler(
    AbstractHandler,
    ProcessorStack,
    FormattableHandlerInterface,
    ABC,
):
    """Handles a record by processing it, formatting it, then writing the text.

    Subclasses implement :meth:`write` alone, and override
    :meth:`default_formatter` if a line of text is the wrong default.
    """

    def __init__(self, level: LevelLike = Level.DEBUG, bubble: bool = True) -> None:
        """Handle records at ``level`` or above, letting them bubble on if ``bubble``."""
        super().__init__(level, bubble)
        self._formatter: FormatterInterface | None = None

    @property
    @override
    def formatter(self) -> FormatterInterface:
        """The formatter in use, built from :meth:`default_formatter` on first use."""
        if self._formatter is None:
            self._formatter = self.default_formatter()
        return self._formatter

    @formatter.setter
    @override
    def formatter(self, formatter: FormatterInterface, /) -> None:
        self._formatter = formatter

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Process, format and write ``record`` if it is at this handler's level."""
        if not self.is_handling(record):
            return False
        record = self._process(record)
        self.write(record, self.formatter.format(record))
        return not self.bubble

    @override
    def reset(self) -> None:
        """Reset every processor of this handler that holds state."""
        super().reset()
        self._reset_processors()

    def default_formatter(self) -> FormatterInterface:
        """The formatter used until another is set: one line of text per record."""
        return LineFormatter()

    @abstractmethod
    def write(self, record: LogRecord, formatted: str) -> None:
        """Write ``formatted``, the rendering of ``record``, wherever this handler writes."""
