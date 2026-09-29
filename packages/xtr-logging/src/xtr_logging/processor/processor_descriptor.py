"""A declared processor, and where it runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ._target import refuse_both_targets

if TYPE_CHECKING:
    from .processor_interface import ProcessorInterface

__all__ = ["ProcessorDescriptor"]


@dataclass(frozen=True, slots=True)
class ProcessorDescriptor:
    """One declared processor, and where it runs.

    Attributes:
        processor: The processor itself — always an instance when read from
            :attr:`~xtr_logging.processor.processor_registry.ProcessorRegistry.descriptors`.
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
        refuse_both_targets(self.channel, self.handler)
