"""A handler that runs processors of its own."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_logging.processor.processor_interface import ProcessorInterface

__all__ = ["ProcessableHandlerInterface"]


@runtime_checkable
class ProcessableHandlerInterface(Protocol):
    """Runs processors on the records it handles, after the logger's own.

    Handlers are shared between channels, so a processor attached here
    applies to records from every channel the handler serves.
    """

    def push_processor(self, processor: ProcessorInterface, /) -> None:
        """Add ``processor`` in front of those already attached."""
        ...

    def pop_processor(self) -> ProcessorInterface:
        """Remove and return the processor added last.

        Raises:
            EmptyStackError: If there is none.
        """
        ...
