"""The custom-message authentication error shows its own key."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError, CustomUserMessageAuthenticationError


def test_it_is_an_authentication_error() -> None:
    assert isinstance(CustomUserMessageAuthenticationError("x"), AuthenticationError)


def test_it_shows_its_key_and_data() -> None:
    error = CustomUserMessageAuthenticationError("Not activated.", message_data={"since": "today"})

    assert error.get_message_key() == "Not activated."
    assert error.get_message_data() == {"since": "today"}
