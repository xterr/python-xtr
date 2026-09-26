"""Keep a random fraction of a flood, when a rough idea is enough."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_service_contracts import ResetInterface

from xtr_logging.exception.empty_stack_error import EmptyStackError
from xtr_logging.exception.invalid_option_error import InvalidOptionError

from .abstract_handler import AbstractHandler
from .handler_interface import HandlerInterface
from .processable_handler_interface import ProcessableHandlerInterface

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeAlias

    from xtr_logging.log_record import LogRecord
    from xtr_logging.processor.processor_interface import ProcessorInterface

    _HandlerFactory: TypeAlias = Callable[
        ["LogRecord | None", "SamplingHandler"],
        HandlerInterface,
    ]

__all__ = ["SamplingHandler"]


@final
class SamplingHandler(AbstractHandler, ProcessableHandlerInterface):
    """Forwards roughly one record in ``factor`` and drops the rest.

    A high-frequency event does not need every occurrence logged; sampling
    keeps the volume — and the cost of the wrapped handler — down while still,
    by the law of large numbers, reflecting what is happening. The decision is
    random per record, so the sampled stream is approximate, not every Nth.

    The random source is injected so a test can seed it and know exactly which
    records survive.
    """

    def __init__(
        self,
        handler: HandlerInterface | _HandlerFactory,
        factor: int,
        *,
        rng: random.Random | None = None,
    ) -> None:
        """Sample about one record in ``factor`` for ``handler``.

        Args:
            handler: The handler sampled records are forwarded to, or a factory.
            factor: The sampling divisor; ``1`` keeps everything, ``10`` keeps
                about a tenth.
            rng: The random source; a fresh :class:`random.Random` by default.

        Raises:
            InvalidOptionError: If ``factor`` is less than ``1``.
        """
        super().__init__()
        if factor < 1:
            raise InvalidOptionError("factor", str(factor), "must be 1 or greater to sample")
        self._handler: HandlerInterface | _HandlerFactory = handler
        self._factor: int = factor
        self._rng: random.Random = rng if rng is not None else random.Random()  # noqa: S311 — sampling, not security
        self._processors: tuple[ProcessorInterface, ...] = ()

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
    def is_handling(self, record: LogRecord, /) -> bool:
        """Whether the wrapped handler would handle ``record`` at all."""
        return self._resolve_handler(record).is_handling(record)

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Forward ``record`` with probability ``1 / factor``; drop it otherwise."""
        if self.is_handling(record) and self._rng.randint(1, self._factor) == 1:
            for processor in self._processors:
                record = processor(record)
            _ = self._resolve_handler(record).handle(record)
        return not self._bubble

    @override
    def reset(self) -> None:
        """Reset this handler's processors and the wrapped handler."""
        for processor in self._processors:
            if isinstance(processor, ResetInterface):
                processor.reset()
        handler = self._resolve_handler()
        if isinstance(handler, ResetInterface):
            handler.reset()

    @override
    def close(self) -> None:
        """Close the wrapped handler."""
        self._resolve_handler().close()

    def _resolve_handler(self, record: LogRecord | None = None) -> HandlerInterface:
        handler = self._handler
        if isinstance(handler, HandlerInterface):
            return handler
        resolved = handler(record, self)
        self._handler = resolved
        return resolved
