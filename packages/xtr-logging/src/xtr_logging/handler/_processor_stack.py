"""The processors a handler runs on its own records."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_service_contracts import ResetInterface

from xtr_logging.exception.empty_stack_error import EmptyStackError

from .processable_handler_interface import ProcessableHandlerInterface

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord
    from xtr_logging.processor.processor_interface import ProcessorInterface

__all__ = ["ProcessorStack"]


class ProcessorStack(ProcessableHandlerInterface):
    """A stack of processors, the one pushed last running first.

    Mixed into every handler that runs processors of its own, so pushing,
    popping, running and resetting them behave the same in each.
    """

    _processors: tuple[ProcessorInterface, ...] = ()

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

    def _process(self, record: LogRecord) -> LogRecord:
        """Return ``record`` as every processor of this handler leaves it."""
        for processor in self._processors:
            record = processor(record)
        return record

    def _reset_processors(self) -> None:
        """Reset every processor of this handler that holds state."""
        for processor in self._processors:
            if isinstance(processor, ResetInterface):
                processor.reset()
