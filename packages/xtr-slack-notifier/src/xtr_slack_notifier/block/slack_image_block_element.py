"""An image placed inside a block."""

from __future__ import annotations

from typing import final

from .abstract_slack_block_element import AbstractSlackBlockElement

__all__ = ["SlackImageBlockElement"]


@final
class SlackImageBlockElement(AbstractSlackBlockElement):
    """A small image beside a section's text, as its accessory."""

    def __init__(self, url: str, text: str) -> None:
        """Show the image at ``url``, described by ``text`` for those who cannot see it."""
        super().__init__()
        self._options.update({"type": "image", "image_url": url, "alt_text": text})
