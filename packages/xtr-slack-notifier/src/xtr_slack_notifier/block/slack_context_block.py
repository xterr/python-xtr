"""Small print under a message: text and images."""

from __future__ import annotations

from typing import Final, Self, final

from xtr_notifier.exception import LogicError

from ._text_object import text_object
from .abstract_slack_block import AbstractSlackBlock

__all__ = ["SlackContextBlock"]

_ELEMENT_LIMIT: Final = 10


@final
class SlackContextBlock(AbstractSlackBlock):
    """Up to ten pieces of secondary text and small images, in one line."""

    def __init__(self) -> None:
        """Start with no element."""
        super().__init__()
        self._options["type"] = "context"
        self._elements: list[dict[str, object]] = []

    def text(
        self, text: str, markdown: bool = True, emoji: bool = True, verbatim: bool = False
    ) -> Self:
        """Add text, as ``mrkdwn`` unless ``markdown`` is false.

        Raises:
            LogicError: When the block already has ten elements.
        """
        return self._add(text_object(text, markdown, emoji, verbatim))

    def image(self, url: str, text: str) -> Self:
        """Add the image at ``url``, described by ``text``.

        Raises:
            LogicError: When the block already has ten elements.
        """
        return self._add({"type": "image", "image_url": url, "alt_text": text})

    def id(self, block_id: str) -> Self:
        """Name the block, so an interaction with it can be told apart."""
        self._options["block_id"] = block_id
        return self

    def _add(self, element: dict[str, object]) -> Self:
        if len(self._elements) == _ELEMENT_LIMIT:
            raise LogicError(f"Maximum number of elements should not exceed {_ELEMENT_LIMIT}.")
        self._elements.append(element)
        self._options["elements"] = self._elements
        return self
