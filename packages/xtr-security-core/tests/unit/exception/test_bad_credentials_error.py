"""The bad-credentials error carries a safe public key."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError, BadCredentialsError


def test_it_is_an_authentication_error() -> None:
    assert isinstance(BadCredentialsError(), AuthenticationError)


def test_its_public_key() -> None:
    assert BadCredentialsError().get_message_key() == "Invalid credentials."
