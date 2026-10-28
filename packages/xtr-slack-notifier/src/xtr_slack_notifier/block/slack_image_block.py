"""An image shown as a block of its own."""

from __future__ import annotations

from typing import final

from .abstract_slack_block import AbstractSlackBlock

__all__ = ["SlackImageBlock"]


@final
class SlackImageBlock(AbstractSlackBlock):
    """An image across the message's width."""

    def __init__(self, url: str, text: str) -> None:
        """Show the image at ``url``, described by ``text`` for those who cannot see it."""
        super().__init__()
        self._options.update({"type": "image", "image_url": url, "alt_text": text})
