"""A title in large bold text."""

from __future__ import annotations

from typing import Final, Self, final

from xtr_notifier.exception import LengthError

from .abstract_slack_block import AbstractSlackBlock

__all__ = ["SlackHeaderBlock"]

_TEXT_LIMIT: Final = 150
_ID_LIMIT: Final = 255


@final
class SlackHeaderBlock(AbstractSlackBlock):
    """Plain text in a large bold font, up to 150 characters."""

    def __init__(self, text: str) -> None:
        """Title the message ``text``.

        Raises:
            LengthError: When ``text`` is over 150 characters.
        """
        super().__init__()
        if len(text) > _TEXT_LIMIT:
            raise LengthError(f"Maximum length for the text is {_TEXT_LIMIT} characters.")
        self._options.update({"type": "header", "text": {"type": "plain_text", "text": text}})

    def id(self, block_id: str) -> Self:
        """Name the block, so an interaction with it can be told apart.

        Raises:
            LengthError: When ``block_id`` is over 255 characters.
        """
        if len(block_id) > _ID_LIMIT:
            raise LengthError(f"Maximum length for the block id is {_ID_LIMIT} characters.")
        self._options["block_id"] = block_id
        return self
