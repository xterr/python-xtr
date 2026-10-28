from __future__ import annotations

import pytest
from xtr_notifier.exception import LengthError

from xtr_slack_notifier.block import SlackHeaderBlock


def test_it_renders_its_text_and_id() -> None:
    assert SlackHeaderBlock("header text").id("header_id").to_array() == {
        "type": "header",
        "text": {"type": "plain_text", "text": "header text"},
        "block_id": "header_id",
    }


def test_it_refuses_a_text_over_150_characters() -> None:
    with pytest.raises(LengthError, match=r"^Maximum length for the text is 150 characters\.$"):
        _ = SlackHeaderBlock("h" * 151)


def test_it_refuses_a_block_id_over_255_characters() -> None:
    header = SlackHeaderBlock("header")

    with pytest.raises(LengthError, match=r"^Maximum length for the block id is 255 characters\.$"):
        _ = header.id("h" * 256)
