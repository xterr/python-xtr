from __future__ import annotations

from xtr_telegram_notifier.reply.markup import AbstractTelegramReplyMarkup, ReplyKeyboardMarkup
from xtr_telegram_notifier.reply.markup.button import KeyboardButton


def test_it_starts_with_no_row() -> None:
    assert ReplyKeyboardMarkup().to_array() == {"keyboard": []}


def test_it_renders_rows_and_flags_in_the_order_set() -> None:
    markup = (
        ReplyKeyboardMarkup()
        .keyboard([KeyboardButton("Yes"), KeyboardButton("No")])
        .keyboard([KeyboardButton("Maybe")])
        .resize_keyboard(True)
        .one_time_keyboard(True)
        .selective(False)
    )

    assert list(markup.to_array().items()) == [
        ("keyboard", [[{"text": "Yes"}, {"text": "No"}], [{"text": "Maybe"}]]),
        ("resize_keyboard", True),
        ("one_time_keyboard", True),
        ("selective", False),
    ]


def test_it_is_a_reply_markup() -> None:
    assert isinstance(ReplyKeyboardMarkup(), AbstractTelegramReplyMarkup)
