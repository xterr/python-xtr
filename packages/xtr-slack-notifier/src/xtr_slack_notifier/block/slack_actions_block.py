"""A row of buttons."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, Self, final

from xtr_notifier.exception import LogicError

from .abstract_slack_block import AbstractSlackBlock
from .slack_button_block_element import SlackButtonBlockElement

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["SlackActionsBlock"]

_BUTTON_LIMIT: Final = 25


@final
class SlackActionsBlock(AbstractSlackBlock):
    """Up to 25 buttons the reader acts on the message with."""

    def __init__(self) -> None:
        """Start with no button."""
        super().__init__()
        self._options["type"] = "actions"
        self._elements: list[dict[str, object]] = []

    def button(
        self,
        text: str,
        url: str | None = None,
        style: str | None = None,
        value: str | None = None,
        confirm: Mapping[str, object] | None = None,
    ) -> Self:
        """Add a :class:`SlackButtonBlockElement` built from the same arguments.

        Raises:
            LogicError: When the block already has 25 buttons.
        """
        if len(self._elements) == _BUTTON_LIMIT:
            raise LogicError(f"Maximum number of buttons should not exceed {_BUTTON_LIMIT}.")
        element = SlackButtonBlockElement(text, url, style, value, confirm)
        self._elements.append(element.to_array())
        self._options["elements"] = self._elements
        return self

    def id(self, block_id: str) -> Self:
        """Name the block, so an interaction with it can be told apart."""
        self._options["block_id"] = block_id
        return self
