from __future__ import annotations

from xtr_telegram_notifier.reply.markup.button import AbstractKeyboardButton, KeyboardButton


def test_it_renders_its_text() -> None:
    assert KeyboardButton("Hi").to_array() == {"text": "Hi"}


def test_it_requests_a_contact_or_a_location() -> None:
    button = KeyboardButton("Share").request_contact(True).request_location(False)

    assert button.to_array() == {
        "text": "Share",
        "request_contact": True,
        "request_location": False,
    }


def test_it_requests_a_poll_of_a_type() -> None:
    assert KeyboardButton("Poll").request_poll_type("quiz").to_array() == {
        "text": "Poll",
        "request_poll": {"type": "quiz"},
    }


def test_it_is_a_keyboard_button() -> None:
    assert isinstance(KeyboardButton("Hi"), AbstractKeyboardButton)
