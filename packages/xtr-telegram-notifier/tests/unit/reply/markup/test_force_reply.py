from __future__ import annotations

from xtr_telegram_notifier.reply.markup import AbstractTelegramReplyMarkup, ForceReply


def test_it_defaults_to_neither_flag() -> None:
    assert ForceReply().to_array() == {"force_reply": False, "selective": False}


def test_it_renders_its_flags() -> None:
    assert ForceReply(True, True).to_array() == {"force_reply": True, "selective": True}


def test_it_is_a_reply_markup() -> None:
    assert isinstance(ForceReply(), AbstractTelegramReplyMarkup)
