"""A line between blocks."""

from __future__ import annotations

from typing import final

from .abstract_slack_block import AbstractSlackBlock

__all__ = ["SlackDividerBlock"]


@final
class SlackDividerBlock(AbstractSlackBlock):
    """A horizontal rule separating the blocks above it from those below."""

    def __init__(self) -> None:
        """Render as a divider."""
        super().__init__()
        self._options["type"] = "divider"
