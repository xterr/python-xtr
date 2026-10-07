"""The user-not-found error hides the identifier behind a safe key."""

from __future__ import annotations

from xtr_security_core.exception import BadCredentialsError, UserNotFoundError


def test_it_is_a_lookup_error() -> None:
    assert isinstance(UserNotFoundError("alice"), LookupError)


def test_it_keeps_the_identifier_but_shows_a_safe_key() -> None:
    error = UserNotFoundError("alice")

    assert error.user_identifier == "alice"
    assert error.get_message_key() == "Invalid credentials."
    assert "alice" in str(error)


def test_its_key_is_identical_to_bad_credentials() -> None:
    assert UserNotFoundError.MESSAGE_KEY == BadCredentialsError.MESSAGE_KEY
