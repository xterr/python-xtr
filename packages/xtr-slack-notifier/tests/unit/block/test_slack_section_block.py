from __future__ import annotations

import pytest
from xtr_notifier.exception import LogicError

from xtr_slack_notifier.block import SlackImageBlockElement, SlackSectionBlock


def test_it_renders_its_text_fields_and_accessory() -> None:
    section = (
        SlackSectionBlock()
        .text("section text")
        .field("section field")
        .field("section field with verbatim", True, True, False)
        .field("section field in plain text with verbatim", False, True, True)
        .accessory(SlackImageBlockElement("https://example.com/image.jpg", "an image"))
    )

    assert section.to_array() == {
        "type": "section",
        "text": {"type": "mrkdwn", "text": "section text", "verbatim": False},
        "fields": [
            {"type": "mrkdwn", "text": "section field", "verbatim": False},
            {"type": "mrkdwn", "text": "section field with verbatim", "verbatim": False},
            {
                "type": "plain_text",
                "text": "section field in plain text with verbatim",
                "emoji": True,
            },
        ],
        "accessory": {
            "type": "image",
            "image_url": "https://example.com/image.jpg",
            "alt_text": "an image",
        },
    }


def test_a_plain_text_carries_the_emoji_flag() -> None:
    assert SlackSectionBlock().text("plain", False, False).to_array() == {
        "type": "section",
        "text": {"type": "plain_text", "text": "plain", "emoji": False},
    }


def test_it_refuses_an_eleventh_field() -> None:
    section = SlackSectionBlock()
    for i in range(10):
        _ = section.field(str(i))

    with pytest.raises(LogicError, match=r"^Maximum number of fields should not exceed 10\.$"):
        _ = section.field("fail")
