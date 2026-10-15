"""The cookie-theft error says a remember-me cookie was used twice."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError, CookieTheftError, SecurityError


def test_it_is_an_authentication_error() -> None:
    assert isinstance(CookieTheftError(), AuthenticationError)
    assert issubclass(CookieTheftError, SecurityError)


def test_its_public_key_names_the_theft() -> None:
    error = CookieTheftError()

    assert error.get_message_key() == "Cookie has already been used by someone else."
    assert error.get_message_data() == {}
