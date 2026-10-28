"""A text box the reader answers in."""

from __future__ import annotations

from typing import Final, final

from xtr_notifier.exception import LengthError

from .abstract_slack_block import AbstractSlackBlock

__all__ = ["SlackPlainTextInputBlock"]

_LABEL_LIMIT: Final = 150
_ACTION_ID_LIMIT: Final = 255
_PLACEHOLDER_LIMIT: Final = 150


@final
class SlackPlainTextInputBlock(AbstractSlackBlock):
    """A labelled plain text input, its value sent back under ``action_id``."""

    def __init__(
        self, label_text: str, action_id: str, placeholder_text: str | None = None
    ) -> None:
        """Label the input, name its value and, optionally, show a placeholder.

        Raises:
            LengthError: When the label or the placeholder is over 150 characters,
                or the action id over 255.
        """
        super().__init__()
        if len(label_text) > _LABEL_LIMIT:
            raise LengthError(f"Maximum length for the label text is {_LABEL_LIMIT} characters.")
        if len(action_id) > _ACTION_ID_LIMIT:
            raise LengthError(f"Maximum length for the action ID is {_ACTION_ID_LIMIT} characters.")
        if placeholder_text and len(placeholder_text) > _PLACEHOLDER_LIMIT:
            raise LengthError(
                f"Maximum length for the placeholder text is {_PLACEHOLDER_LIMIT} characters."
            )
        element: dict[str, object] = {"type": "plain_text_input", "action_id": action_id}
        if placeholder_text:
            element["placeholder"] = {"type": "plain_text", "text": placeholder_text}
        self._options.update(
            {
                "type": "input",
                "element": element,
                "label": {"type": "plain_text", "text": label_text},
            }
        )
