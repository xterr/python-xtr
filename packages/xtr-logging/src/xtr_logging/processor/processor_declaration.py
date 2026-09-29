"""One ``@as_processor`` declaration: the channel or handler it targets, and its priority."""

from __future__ import annotations

from dataclasses import dataclass

from ._target import refuse_both_targets

__all__ = ["ProcessorDeclaration"]


@dataclass(frozen=True, slots=True)
class ProcessorDeclaration:
    """One declaration on a class or a function: what channel or handler, and priority."""

    channel: str | None = None
    handler: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        """Refuse targeting both a channel and a handler."""
        refuse_both_targets(self.channel, self.handler)
