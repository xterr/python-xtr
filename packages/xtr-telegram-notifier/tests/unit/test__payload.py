from __future__ import annotations

import pytest

from xtr_telegram_notifier._payload import (
    action_for,
    build_input_media,
    expand_options,
    form_fields,
    method_for,
    non_empty,
    text_option_for,
)


@pytest.mark.parametrize(
    ("options", "method"),
    [
        ({}, "sendMessage"),
        ({"message_id": 1}, "editMessageText"),
        ({"message_id": 1, "edit_caption": True}, "editMessageCaption"),
        ({"message_id": 1, "video": "v"}, "editMessageMedia"),
        ({"callback_query_id": "q"}, "answerCallbackQuery"),
        ({"venue": {}}, "sendVenue"),
        ({"contact": {}}, "sendContact"),
        ({"photo": None}, "sendMessage"),
    ],
)
def test_the_options_set_pick_the_method(options: dict[str, object], method: str) -> None:
    assert method_for(options) == method


@pytest.mark.parametrize(
    ("options", "action"),
    [
        ({}, "post"),
        ({"message_id": 1}, "edit"),
        ({"callback_query_id": "q"}, "answer callback query"),
    ],
)
def test_the_action_names_what_the_send_does(options: dict[str, object], action: str) -> None:
    assert action_for(options) == action


@pytest.mark.parametrize(
    ("options", "text_option"),
    [({}, "text"), ({"edit_caption": True}, "caption"), ({"sticker": "s"}, None)],
)
def test_the_text_goes_where_the_kind_of_message_puts_it(
    options: dict[str, object], text_option: str | None
) -> None:
    assert text_option_for(options) == text_option


def test_an_edit_without_media_is_left_as_it_is() -> None:
    options: dict[str, object] = {"message_id": 1, "caption": "c"}

    assert build_input_media(options, "text") == options


def test_a_spoiler_is_left_out_of_a_media_that_cannot_carry_one() -> None:
    built = build_input_media({"message_id": 1, "audio": "a", "has_spoiler": True}, "t")

    assert built == {
        "message_id": 1,
        "media": {"type": "audio", "media": "a", "caption": "t"},
    }


def test_an_expanded_option_that_is_not_a_mapping_is_dropped() -> None:
    assert expand_options({"contact": "x", "venue": None, "a": 1}, "contact", "venue") == {
        "venue": None,
        "a": 1,
    }


def test_empty_fields_are_dropped() -> None:
    assert non_empty({"a": None, "b": False, "c": 0, "d": "", "e": [], "f": "x", "g": True}) == {
        "f": "x",
        "g": True,
    }


def test_a_form_field_holding_a_mapping_or_a_list_becomes_json_text() -> None:
    assert form_fields(
        {"reply_markup": {"a": [1]}, "media": [{"x": 1}], "chat_id": "42", "flag": True, "n": 3}
    ) == {
        "reply_markup": '{"a": [1]}',
        "media": '[{"x": 1}]',
        "chat_id": "42",
        "flag": True,
        "n": 3,
    }
