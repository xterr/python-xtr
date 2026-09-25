"""Declaring a processor where it is written, for a factory to attach."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeVar

from xtr_logging.processor.processor_registry import (
    ProcessorDescriptor,
    default_processor_registry,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_logging.processor.processor_interface import ProcessorInterface
    from xtr_logging.processor.processor_registry import ProcessorRegistry

__all__ = ["as_processor"]

P = TypeVar("P", bound="ProcessorInterface | type[ProcessorInterface]")


def as_processor(
    *,
    channel: str | None = None,
    handler: str | None = None,
    priority: int = 0,
    registry: ProcessorRegistry | None = None,
) -> Callable[[P], P]:
    """Declare the decorated function or class as a processor.

    A function is the processor. A class is built once, with no arguments,
    as it is declared; its instance is the processor. Either way the
    decorated object is returned unchanged::

        @as_processor(channel="billing")
        def add_tenant(record: LogRecord) -> LogRecord:
            return record.with_extra({"tenant": current_tenant()})

    A :class:`~xtr_logging.logger_factory.LoggerFactory` attaches every
    declared processor to the loggers it builds — so import the declaring
    module first.

    Args:
        channel: Run only on this channel.
        handler: Run inside this handler instead; handlers are shared, so it
            then applies to every channel the handler serves.
        priority: Higher runs first.
        registry: Declare here instead of the process-wide registry.

    Raises:
        InvalidOptionError: If both ``channel`` and ``handler`` are given.
    """
    target_registry = registry if registry is not None else default_processor_registry()

    def declare(target: P) -> P:
        processor: ProcessorInterface = target() if isinstance(target, type) else target
        target_registry.register(ProcessorDescriptor(processor, channel, handler, priority))
        return target

    return declare
