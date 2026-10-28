from __future__ import annotations

import pytest
from xtr_notifier.exception import LengthError

from xtr_slack_notifier.block import SlackPlainTextInputBlock


def test_it_renders_a_placeholder() -> None:
    block = SlackPlainTextInputBlock("Time spent", "time_spent_input", "Enter some text here")

    assert block.to_array() == {
        "type": "input",
        "element": {
            "type": "plain_text_input",
            "action_id": "time_spent_input",
            "placeholder": {"type": "plain_text", "text": "Enter some text here"},
        },
        "label": {"type": "plain_text", "text": "Time spent"},
    }


def test_it_renders_without_a_placeholder() -> None:
    assert SlackPlainTextInputBlock("Time spent", "time_spent_input").to_array() == {
        "type": "input",
        "element": {"type": "plain_text_input", "action_id": "time_spent_input"},
        "label": {"type": "plain_text", "text": "Time spent"},
    }


def test_it_refuses_a_label_over_150_characters() -> None:
    with pytest.raises(
        LengthError, match=r"^Maximum length for the label text is 150 characters\.$"
    ):
        _ = SlackPlainTextInputBlock("a" * 151, "time_spent_input")


def test_it_refuses_an_action_id_over_255_characters() -> None:
    with pytest.raises(
        LengthError, match=r"^Maximum length for the action ID is 255 characters\.$"
    ):
        _ = SlackPlainTextInputBlock("Time spent", "a" * 256)


def test_it_refuses_a_placeholder_over_150_characters() -> None:
    with pytest.raises(
        LengthError, match=r"^Maximum length for the placeholder text is 150 characters\.$"
    ):
        _ = SlackPlainTextInputBlock("Time spent", "time_spent_input", "a" * 151)
