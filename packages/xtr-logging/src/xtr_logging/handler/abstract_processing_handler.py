"""A handler that runs its own processors, formats, and writes."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_logging_contracts import Level
from xtr_service_contracts import ResettableInterface

from xtr_logging.exception.empty_stack_error import EmptyStackError
from xtr_logging.formatter.line_formatter import LineFormatter

from .abstract_handler import AbstractHandler
from .formattable_handler_interface import FormattableHandlerInterface
from .processable_handler_interface import ProcessableHandlerInterface

if TYPE_CHECKING:
    from xtr_logging_contracts import LevelLike

    from xtr_logging.formatter.formatter_interface import FormatterInterface
    from xtr_logging.log_record import LogRecord
    from xtr_logging.processor.processor_interface import ProcessorInterface

__all__ = ["AbstractProcessingHandler"]


class AbstractProcessingHandler(
    AbstractHandler,
    ProcessableHandlerInterface,
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
        self._processors: tuple[ProcessorInterface, ...] = ()
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

    @property
    def processors(self) -> tuple[ProcessorInterface, ...]:
        """This handler's own processors, in the order they run."""
        return self._processors

    @override
    def push_processor(self, processor: ProcessorInterface, /) -> None:
        """Add ``processor`` in front of those already attached."""
        self._processors = (processor, *self._processors)

    @override
    def pop_processor(self) -> ProcessorInterface:
        """Remove and return the processor that runs first.

        Raises:
            EmptyStackError: If there is none.
        """
        if not self._processors:
            raise EmptyStackError(type(self).__name__, "processor")
        first, *rest = self._processors
        self._processors = tuple(rest)
        return first

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Process, format and write ``record`` if it is at this handler's level."""
        if not self.is_handling(record):
            return False
        for processor in self._processors:
            record = processor(record)
        self.write(record, self.formatter.format(record))
        return not self.bubble

    @override
    def reset(self) -> None:
        """Reset every processor of this handler that holds state."""
        super().reset()
        for processor in self._processors:
            if isinstance(processor, ResettableInterface):
                processor.reset()

    def default_formatter(self) -> FormatterInterface:
        """The formatter used until another is set: one line of text per record."""
        return LineFormatter()

    @abstractmethod
    def write(self, record: LogRecord, formatted: str) -> None:
        """Write ``formatted``, the rendering of ``record``, wherever this handler writes."""
