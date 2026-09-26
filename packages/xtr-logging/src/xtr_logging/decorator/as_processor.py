"""Declaring a processor where it is written, for a factory to attach."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, TypeVar, cast

from xtr_logging.processor.processor_registry import (
    PROCESSORS_ATTRIBUTE,
    ProcessorDeclaration,
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

    A function is the processor. A class is stored as-is: the container
    instantiates it in a kernel, or the registry does so lazily the first
    time :attr:`~xtr_logging.processor.processor_registry.ProcessorRegistry.descriptors`
    is read. Either way the decorated object is returned unchanged::

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
    declaration = ProcessorDeclaration(channel=channel, handler=handler, priority=priority)

    def declare(target: P) -> P:
        if isinstance(target, type):
            target_registry.register_class(
                cast("type[ProcessorInterface]", target),
                channel=declaration.channel,
                handler=declaration.handler,
                priority=declaration.priority,
            )
        else:
            target_registry.register(
                ProcessorDescriptor(target, declaration.channel, declaration.handler, priority)
            )
        # Recorded on the class or the function itself too, so a kernel's scan finds it
        # and attaches it to that kernel's loggers — not only the process-wide registry.
        existing: object = getattr(target, PROCESSORS_ATTRIBUTE, ())
        previous = (
            cast("tuple[ProcessorDeclaration, ...]", existing)
            if isinstance(existing, tuple)
            else ()
        )
        with contextlib.suppress(AttributeError, TypeError):
            setattr(target, PROCESSORS_ATTRIBUTE, (*previous, declaration))
        return target

    return declare
