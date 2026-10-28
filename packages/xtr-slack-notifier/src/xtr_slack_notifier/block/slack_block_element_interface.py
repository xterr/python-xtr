"""An element placed inside a Slack block."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["SlackBlockElementInterface"]


@runtime_checkable
class SlackBlockElementInterface(Protocol):
    """An interactive or visual element inside a block: a button, an image."""

    def to_array(self) -> dict[str, object]:
        """Render the element as the Web API reads it."""
        ...
