"""A block of text, with fields and an accessory."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Self, final

from xtr_notifier.exception import LogicError

from ._text_object import text_object
from .abstract_slack_block import AbstractSlackBlock

if TYPE_CHECKING:
    from .slack_block_element_interface import SlackBlockElementInterface

__all__ = ["SlackSectionBlock"]

_FIELD_LIMIT: Final = 10


@final
class SlackSectionBlock(AbstractSlackBlock):
    """Text, up to ten fields laid out in two columns, and an element beside them."""

    def __init__(self) -> None:
        """Start with no text."""
        super().__init__()
        self._options["type"] = "section"
        self._fields: list[dict[str, object]] = []

    def text(
        self, text: str, markdown: bool = True, emoji: bool = True, verbatim: bool = False
    ) -> Self:
        """Set the section's text, as ``mrkdwn`` unless ``markdown`` is false."""
        self._options["text"] = text_object(text, markdown, emoji, verbatim)
        return self

    def field(
        self, text: str, markdown: bool = True, emoji: bool = True, verbatim: bool = False
    ) -> Self:
        """Add a field, as ``mrkdwn`` unless ``markdown`` is false.

        Raises:
            LogicError: When the section already has ten fields.
        """
        if len(self._fields) == _FIELD_LIMIT:
            raise LogicError(f"Maximum number of fields should not exceed {_FIELD_LIMIT}.")
        self._fields.append(text_object(text, markdown, emoji, verbatim))
        self._options["fields"] = self._fields
        return self

    def accessory(self, element: SlackBlockElementInterface) -> Self:
        """Show ``element`` beside the text."""
        self._options["accessory"] = element.to_array()
        return self
