"""A block of a Slack message's layout."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["SlackBlockInterface"]


@runtime_checkable
class SlackBlockInterface(Protocol):
    """One block of a message's Block Kit layout: a section, a divider, a row of buttons."""

    def to_array(self) -> dict[str, object]:
        """Render the block as the Web API reads it."""
        ...
