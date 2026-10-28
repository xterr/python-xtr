"""The invalid-login-link authentication error: the flow's one answer."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError

from xtr_security_http.exception import InvalidLoginLinkAuthenticationError


def test_it_is_an_authentication_error() -> None:
    assert isinstance(InvalidLoginLinkAuthenticationError(), AuthenticationError)


def test_its_public_message_names_the_link() -> None:
    error = InvalidLoginLinkAuthenticationError("Login link could not be validated.")

    assert error.get_message_key() == "Invalid or expired login link."
    assert str(error) == "Login link could not be validated."
