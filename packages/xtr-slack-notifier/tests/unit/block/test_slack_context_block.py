from __future__ import annotations

import pytest
from xtr_notifier.exception import LogicError

from xtr_slack_notifier.block import SlackContextBlock


def test_it_renders_its_elements_and_id() -> None:
    context = (
        SlackContextBlock()
        .text("context text without emoji", False, False)
        .text("context text verbatim", True, False, True)
        .image("https://example.com/image.jpg", "an image")
        .id("context_id")
    )

    assert context.to_array() == {
        "type": "context",
        "elements": [
            {"type": "plain_text", "text": "context text without emoji", "emoji": False},
            {"type": "mrkdwn", "text": "context text verbatim", "verbatim": True},
            {
                "type": "image",
                "image_url": "https://example.com/image.jpg",
                "alt_text": "an image",
            },
        ],
        "block_id": "context_id",
    }


@pytest.mark.parametrize("last", ["text", "image"])
def test_it_refuses_an_eleventh_element(last: str) -> None:
    context = SlackContextBlock()
    for i in range(10):
        _ = context.text(str(i)) if i % 2 == 0 else context.image(str(i), str(i))

    with pytest.raises(LogicError, match=r"^Maximum number of elements should not exceed 10\.$"):
        _ = context.text("fail") if last == "text" else context.image("fail", "fail")
