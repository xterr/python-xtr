"""One ``@as_processor`` declaration: the channel or handler it targets, and its priority."""

from __future__ import annotations

from dataclasses import dataclass

from xtr_logging.exception.invalid_option_error import InvalidOptionError

__all__ = ["ProcessorDeclaration"]


@dataclass(frozen=True, slots=True)
class ProcessorDeclaration:
    """One declaration on a class or a function: what channel or handler, and priority."""

    channel: str | None = None
    handler: str | None = None
    priority: int = 0

    def __post_init__(self) -> None:
        """Refuse targeting both a channel and a handler."""
        if self.channel is not None and self.handler is not None:
            raise InvalidOptionError(
                "channel",
                self.channel,
                f"a processor targets a channel or a handler, not both (handler={self.handler})",
            )
