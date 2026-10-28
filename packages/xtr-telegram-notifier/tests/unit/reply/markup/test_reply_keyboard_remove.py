from __future__ import annotations

from xtr_telegram_notifier.reply.markup import AbstractTelegramReplyMarkup, ReplyKeyboardRemove


def test_it_defaults_to_neither_flag() -> None:
    assert ReplyKeyboardRemove().to_array() == {"remove_keyboard": False, "selective": False}


def test_it_renders_its_flags() -> None:
    assert ReplyKeyboardRemove(True, True).to_array() == {
        "remove_keyboard": True,
        "selective": True,
    }


def test_it_is_a_reply_markup() -> None:
    assert isinstance(ReplyKeyboardRemove(), AbstractTelegramReplyMarkup)
