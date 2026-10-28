"""A button attached to a message."""

from __future__ import annotations

from typing import Self, final

from .abstract_keyboard_button import AbstractKeyboardButton

__all__ = ["InlineKeyboardButton"]


@final
class InlineKeyboardButton(AbstractKeyboardButton):
    """A button under a message: it opens a link, logs in, calls the bot back, or pays.

    The bot API wants exactly one action per button; which one is set is left
    to the caller, as the API reports a button with none or several.
    """

    def __init__(self, text: str = "") -> None:
        """Label the button ``text``."""
        super().__init__()
        self._options["text"] = text
        self._login_url: dict[str, object] = {}

    def url(self, url: str) -> Self:
        """Open ``url`` when tapped."""
        self._options["url"] = url
        return self

    def login_url(self, url: str) -> Self:
        """Log the user in to ``url`` when tapped."""
        self._login_option("url", url)
        return self

    def login_url_forward_text(self, text: str) -> Self:
        """Label the button ``text`` in a forwarded copy of the message."""
        self._login_option("forward_text", text)
        return self

    def request_write_access(self, request: bool) -> Self:
        """Ask the user, on login, to let the bot message them."""
        self._login_option("request_write_access", request)
        return self

    def callback_data(self, data: str) -> Self:
        """Send ``data`` back to the bot as a callback query when tapped."""
        self._options["callback_data"] = data
        return self

    def switch_inline_query(self, query: str) -> Self:
        """Pick a chat and start an inline query for ``query`` in it when tapped."""
        self._options["switch_inline_query"] = query
        return self

    def pay_button(self, pay: bool) -> Self:
        """Make it the message's payment button."""
        self._options["pay"] = pay
        return self

    def _login_option(self, key: str, value: object) -> None:
        """Set one field of the login URL, placing the login URL where it was first set."""
        self._login_url[key] = value
        self._options["login_url"] = self._login_url
