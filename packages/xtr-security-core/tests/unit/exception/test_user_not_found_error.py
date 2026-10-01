"""The user-not-found error hides the identifier behind a safe key."""

from __future__ import annotations

from xtr_security_core.exception import UserNotFoundError


def test_it_is_a_lookup_error() -> None:
    assert isinstance(UserNotFoundError("alice"), LookupError)


def test_it_keeps_the_identifier_but_shows_a_safe_key() -> None:
    error = UserNotFoundError("alice")

    assert error.user_identifier == "alice"
    assert error.get_message_key() == "Bad credentials."
    assert "alice" in str(error)
