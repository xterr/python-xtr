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


def test_a_session_keeps_none_of_the_identifier() -> None:
    assert "alice" not in str(UserNotFoundError("alice").to_session())


def test_it_is_rebuilt_from_a_session_naming_no_identifier() -> None:
    rebuilt = UserNotFoundError.from_session(UserNotFoundError.MESSAGE_KEY, {})

    assert type(rebuilt) is UserNotFoundError
    assert rebuilt.user_identifier is None
    assert str(rebuilt) == "Invalid credentials."
