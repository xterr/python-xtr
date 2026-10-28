from __future__ import annotations

from xtr_telegram_notifier.reply.markup import AbstractTelegramReplyMarkup, InlineKeyboardMarkup
from xtr_telegram_notifier.reply.markup.button import InlineKeyboardButton


def test_it_starts_with_no_row() -> None:
    assert InlineKeyboardMarkup().to_array() == {"inline_keyboard": []}


def test_each_call_adds_a_row_of_buttons() -> None:
    markup = InlineKeyboardMarkup()

    returned = markup.inline_keyboard([InlineKeyboardButton("A"), InlineKeyboardButton("B")])
    _ = markup.inline_keyboard([InlineKeyboardButton("C")])

    assert returned is markup
    assert markup.to_array() == {
        "inline_keyboard": [[{"text": "A"}, {"text": "B"}], [{"text": "C"}]]
    }


def test_it_is_a_reply_markup() -> None:
    assert isinstance(InlineKeyboardMarkup(), AbstractTelegramReplyMarkup)


def test_its_array_is_a_copy() -> None:
    markup = InlineKeyboardMarkup()

    array = markup.to_array()
    _ = markup.inline_keyboard([InlineKeyboardButton("A")])

    assert array == {"inline_keyboard": []}
