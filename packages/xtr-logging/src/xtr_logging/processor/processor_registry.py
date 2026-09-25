"""Processors declared in code, waiting for a factory to attach them."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from xtr_logging.exception.invalid_option_error import InvalidOptionError

if TYPE_CHECKING:
    from .processor_interface import ProcessorInterface

__all__ = ["ProcessorDescriptor", "ProcessorRegistry", "default_processor_registry"]


@dataclass(frozen=True, slots=True)
class ProcessorDescriptor:
    """One declared processor, and where it runs.

    Attributes:
        processor: The processor itself.
        channel: Run only on this channel's logger.
        handler: Run inside this handler instead of on a logger.
        priority: Higher runs first; ties keep declaration order.
    """

    processor: ProcessorInterface
    channel: str | None = None
    handler: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        """Refuse targeting both a channel and a handler.

        Raises:
            InvalidOptionError: If both are given.
        """
        if self.channel is not None and self.handler is not None:
            raise InvalidOptionError(
                "channel",
                self.channel,
                f"a processor targets a channel or a handler, not both (handler={self.handler})",
            )


@final
class ProcessorRegistry:
    """Holds declared processors until a factory attaches them.

    :func:`~xtr_logging.decorator.as_processor` writes to the process-wide
    one by default, which is what lets a module declare a processor without
    importing the factory. Pass a registry of your own to keep two
    applications — or two tests — apart.
    """

    __slots__ = ("_descriptors",)

    def __init__(self) -> None:
        """Start empty."""
        self._descriptors: list[ProcessorDescriptor] = []

    @property
    def descriptors(self) -> tuple[ProcessorDescriptor, ...]:
        """Every declared processor, in declaration order."""
        return tuple(self._descriptors)

    def register(self, descriptor: ProcessorDescriptor) -> None:
        """Declare ``descriptor``."""
        self._descriptors.append(descriptor)

    def clear(self) -> None:
        """Forget every declared processor."""
        self._descriptors.clear()


_DEFAULT = ProcessorRegistry()


def default_processor_registry() -> ProcessorRegistry:
    """Return the process-wide registry :func:`as_processor` declares into."""
    return _DEFAULT
