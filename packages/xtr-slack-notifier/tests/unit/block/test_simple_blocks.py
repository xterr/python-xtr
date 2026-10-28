from __future__ import annotations

from xtr_slack_notifier.block import (
    AbstractSlackBlock,
    AbstractSlackBlockElement,
    SlackBlockElementInterface,
    SlackBlockInterface,
    SlackButtonBlockElement,
    SlackDividerBlock,
    SlackImageBlock,
    SlackImageBlockElement,
)


def test_a_divider_is_its_type_alone() -> None:
    assert SlackDividerBlock().to_array() == {"type": "divider"}


def test_an_image_block_renders_its_url_and_alt_text() -> None:
    assert SlackImageBlock("https://example.com/a.png", "alt").to_array() == {
        "type": "image",
        "image_url": "https://example.com/a.png",
        "alt_text": "alt",
    }


def test_an_image_element_renders_its_url_and_alt_text() -> None:
    assert SlackImageBlockElement("https://example.com/a.png", "alt").to_array() == {
        "type": "image",
        "image_url": "https://example.com/a.png",
        "alt_text": "alt",
    }


def test_a_button_leaves_out_what_is_empty() -> None:
    assert SlackButtonBlockElement("Go", "", "", "", {}).to_array() == {
        "type": "button",
        "text": {"type": "plain_text", "text": "Go"},
    }


def test_blocks_and_elements_implement_their_interfaces() -> None:
    assert isinstance(SlackDividerBlock(), AbstractSlackBlock)
    assert isinstance(SlackDividerBlock(), SlackBlockInterface)
    assert isinstance(SlackButtonBlockElement("Go"), AbstractSlackBlockElement)
    assert isinstance(SlackButtonBlockElement("Go"), SlackBlockElementInterface)


def test_a_rendered_block_is_a_copy() -> None:
    block = SlackImageBlock("https://example.com/a.png", "alt")

    rendered = block.to_array()
    rendered["alt_text"] = "changed"

    assert block.to_array()["alt_text"] == "alt"
