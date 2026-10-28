from __future__ import annotations

import pytest
from xtr_notifier.message import MessageOptions, MessageOptionsInterface

from xtr_telegram_notifier import TelegramOptions
from xtr_telegram_notifier.reply.markup import InlineKeyboardMarkup
from xtr_telegram_notifier.reply.markup.button import InlineKeyboardButton


@pytest.mark.parametrize("cache_time", [1, 2, 10])
def test_it_answers_a_callback_query_with_a_cache_time(cache_time: int) -> None:
    options = TelegramOptions()

    returned = options.answer_callback_query("123", True, cache_time)

    assert returned is options
    assert options.to_options().values == {
        "callback_query_id": "123",
        "show_alert": True,
        "cache_time": cache_time,
    }


@pytest.mark.parametrize("cache_time", [0, -1, -10])
def test_it_answers_a_callback_query_without_a_cache_time_below_one(cache_time: int) -> None:
    options = TelegramOptions()

    returned = options.answer_callback_query("123", True, cache_time)

    assert returned is options
    assert options.to_options().values == {"callback_query_id": "123", "show_alert": True}


def test_it_edits_a_message() -> None:
    options = TelegramOptions()

    returned = options.edit(123)

    assert returned is options
    assert options.to_options().values == {"message_id": 123}


def test_it_edits_a_caption() -> None:
    options = TelegramOptions()

    returned = options.edit_caption(123)

    assert returned is options
    assert options.to_options().values == {"message_id": 123, "edit_caption": True}


def test_it_starts_from_the_options_given() -> None:
    options = TelegramOptions({"chat_id": "123456", "parse_mode": "HTML"})

    assert options.to_options() == MessageOptions(
        "telegram", "123456", {"chat_id": "123456", "parse_mode": "HTML"}
    )
    assert options.recipient_id == "123456"


def test_it_renders_every_method_in_the_order_called() -> None:
    options = (
        TelegramOptions()
        .chat_id("123456")
        .parse_mode(TelegramOptions.PARSE_MODE_MARKDOWN_V2)
        .disable_web_page_preview(True)
        .disable_notification(True)
        .reply_to(789)
    )

    assert list(options.to_options().values.items()) == [
        ("chat_id", "123456"),
        ("parse_mode", "MarkdownV2"),
        ("disable_web_page_preview", True),
        ("disable_notification", True),
        ("reply_to_message_id", 789),
    ]
    assert options.recipient_id == "123456"


def test_its_parse_modes_are_the_bot_apis() -> None:
    assert TelegramOptions.PARSE_MODE_HTML == "HTML"
    assert TelegramOptions.PARSE_MODE_MARKDOWN == "Markdown"
    assert TelegramOptions.PARSE_MODE_MARKDOWN_V2 == "MarkdownV2"


def test_it_carries_a_reply_markup() -> None:
    markup = InlineKeyboardMarkup().inline_keyboard(
        [
            InlineKeyboardButton("Button 1").url("https://example.com"),
            InlineKeyboardButton("Button 2").callback_data("callback_2"),
        ]
    )

    options = TelegramOptions().chat_id("123456").reply_markup(markup)

    assert options.to_options().values == {
        "chat_id": "123456",
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "Button 1", "url": "https://example.com"},
                    {"text": "Button 2", "callback_data": "callback_2"},
                ]
            ]
        },
    }


def test_its_methods_chain() -> None:
    options = TelegramOptions()

    result = (
        options.chat_id("987654")
        .parse_mode(TelegramOptions.PARSE_MODE_HTML)
        .disable_notification(False)
    )

    assert result is options
    assert options.to_options().values == {
        "chat_id": "987654",
        "parse_mode": "HTML",
        "disable_notification": False,
    }


def test_it_starts_empty() -> None:
    options = TelegramOptions()

    assert options.to_options() == MessageOptions("telegram")
    assert options.recipient_id is None


def test_it_is_a_message_options_builder() -> None:
    assert isinstance(TelegramOptions(), MessageOptionsInterface)


def test_it_sets_the_remaining_scalar_options() -> None:
    options = (
        TelegramOptions()
        .message_thread_id(7)
        .protect_content(True)
        .has_spoiler(True)
        .photo("https://localhost/photo.png")
    )

    assert options.to_options().values == {
        "message_thread_id": 7,
        "protect_content": True,
        "has_spoiler": True,
        "photo": "https://localhost/photo.png",
    }


def test_it_collects_uploads_by_option() -> None:
    options = (
        TelegramOptions()
        .upload_photo("photo.png")
        .upload_document("doc.pdf")
        .upload_video("video.mp4")
        .upload_audio("audio.ogg")
        .upload_animation("animation.gif")
        .upload_sticker("sticker.webp", "🤖")
    )

    assert options.to_options().values == {
        "upload": {
            "photo": "photo.png",
            "document": "doc.pdf",
            "video": "video.mp4",
            "audio": "audio.ogg",
            "animation": "animation.gif",
            "sticker": "sticker.webp",
        },
        "emoji": "🤖",
    }


def test_a_sticker_without_an_emoji_sets_none() -> None:
    assert TelegramOptions().sticker("ABC").to_options().values == {
        "sticker": "ABC",
        "emoji": None,
    }


def test_it_sets_a_location_and_a_venue() -> None:
    assert TelegramOptions().location(1.5, 2.5).to_options().values == {
        "location": {"latitude": 1.5, "longitude": 2.5}
    }
    assert TelegramOptions().venue(1.5, 2.5, "Title", "Address").to_options().values == {
        "venue": {"latitude": 1.5, "longitude": 2.5, "title": "Title", "address": "Address"}
    }


def test_a_contact_carries_its_optional_fields_only_when_given() -> None:
    assert TelegramOptions().contact("+33", "John").to_options().values == {
        "contact": {"phone_number": "+33", "first_name": "John"}
    }
    assert TelegramOptions().contact("+33", "John", "Doe", "VCARD").to_options().values == {
        "contact": {
            "phone_number": "+33",
            "first_name": "John",
            "last_name": "Doe",
            "vcard": "VCARD",
        }
    }


def test_the_rendered_options_do_not_change_with_the_builder() -> None:
    options = TelegramOptions().upload_photo("a.png")
    rendered = options.to_options()

    _ = options.upload_video("b.mp4")

    assert rendered.values == {"upload": {"photo": "a.png"}}


def test_the_options_given_are_copied() -> None:
    given: dict[str, object] = {"chat_id": "1"}
    options = TelegramOptions(given)

    given["chat_id"] = "2"

    assert options.recipient_id == "1"


def test_a_numeric_chat_id_is_read_as_text() -> None:
    assert TelegramOptions({"chat_id": -100123}).recipient_id == "-100123"
