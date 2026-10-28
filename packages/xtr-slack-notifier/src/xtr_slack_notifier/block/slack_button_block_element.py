"""A button inside a block."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from .abstract_slack_block_element import AbstractSlackBlockElement

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["SlackButtonBlockElement"]


@final
class SlackButtonBlockElement(AbstractSlackBlockElement):
    """A button that opens a link or sends a value back to the app."""

    def __init__(
        self,
        text: str,
        url: str | None = None,
        style: str | None = None,
        value: str | None = None,
        confirm: Mapping[str, object] | None = None,
    ) -> None:
        """Label the button ``text``; each other field is sent only when given and not empty.

        Args:
            text: The label.
            url: The link the button opens.
            style: ``primary`` or ``danger``.
            value: What the app receives when the button is clicked.
            confirm: A confirmation dialog shown before the click goes through.
        """
        super().__init__()
        self._options.update({"type": "button", "text": {"type": "plain_text", "text": text}})
        for key, field in (("url", url), ("style", style), ("value", value)):
            if field:
                self._options[key] = field
        if confirm:
            self._options["confirm"] = dict(confirm)
