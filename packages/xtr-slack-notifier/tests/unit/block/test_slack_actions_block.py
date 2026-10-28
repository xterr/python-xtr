from __future__ import annotations

import pytest
from xtr_notifier.exception import LogicError

from xtr_slack_notifier.block import SlackActionsBlock, SlackBlockInterface

_CONFIRM: dict[str, object] = {
    "title": {"type": "plain_text", "text": "test-confirm-title-4"},
    "text": {"type": "plain_text", "text": "test-confirm-text-4"},
    "confirm": {"type": "plain_text", "text": "test-confirm-confirm-4"},
    "deny": {"type": "plain_text", "text": "test-confirm-deny-4"},
    "style": "danger",
}


def test_it_renders_its_buttons() -> None:
    actions = (
        SlackActionsBlock()
        .button("first button text", "https://example.org", None, "test-value")
        .button("second button text", "https://example.org/slack", "danger")
        .button("third button text", None, None, "test-value-3")
        .button("fourth button text", None, None, "test-value-4", _CONFIRM)
    )

    assert actions.to_array() == {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "first button text"},
                "url": "https://example.org",
                "value": "test-value",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "second button text"},
                "url": "https://example.org/slack",
                "style": "danger",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "third button text"},
                "value": "test-value-3",
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "fourth button text"},
                "value": "test-value-4",
                "confirm": _CONFIRM,
            },
        ],
    }


def test_it_refuses_a_twenty_sixth_button() -> None:
    actions = SlackActionsBlock()
    for i in range(25):
        _ = actions.button(str(i), str(i))

    with pytest.raises(LogicError, match=r"^Maximum number of buttons should not exceed 25\.$"):
        _ = actions.button("fail", "fail")


def test_it_carries_a_block_id() -> None:
    assert SlackActionsBlock().id("actions_id").to_array() == {
        "type": "actions",
        "block_id": "actions_id",
    }


def test_it_is_a_block() -> None:
    assert isinstance(SlackActionsBlock(), SlackBlockInterface)
