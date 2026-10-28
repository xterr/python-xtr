from __future__ import annotations

from xtr_telegram_notifier.reply.markup.button import AbstractKeyboardButton, InlineKeyboardButton


def test_it_defaults_to_an_empty_text() -> None:
    assert InlineKeyboardButton().to_array() == {"text": ""}


def test_it_renders_every_option_in_the_order_set() -> None:
    button = (
        InlineKeyboardButton("Pay")
        .url("https://example.com")
        .login_url("https://example.com/login")
        .login_url_forward_text("Log in")
        .request_write_access(True)
        .callback_data("data")
        .switch_inline_query("query")
        .pay_button(True)
    )

    assert list(button.to_array().items()) == [
        ("text", "Pay"),
        ("url", "https://example.com"),
        (
            "login_url",
            {
                "url": "https://example.com/login",
                "forward_text": "Log in",
                "request_write_access": True,
            },
        ),
        ("callback_data", "data"),
        ("switch_inline_query", "query"),
        ("pay", True),
    ]


def test_its_array_is_a_copy() -> None:
    button = InlineKeyboardButton("A").login_url("https://example.com")

    array = button.to_array()
    _ = button.login_url_forward_text("later")

    assert array == {"text": "A", "login_url": {"url": "https://example.com"}}


def test_it_is_a_keyboard_button() -> None:
    assert isinstance(InlineKeyboardButton(), AbstractKeyboardButton)
