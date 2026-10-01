"""The authentication base error keeps its internal and public text apart."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError, SecurityError


def test_it_is_a_security_error() -> None:
    assert issubclass(AuthenticationError, SecurityError)


def test_its_default_public_key_and_data() -> None:
    error = AuthenticationError()

    assert error.get_message_key() == "An authentication exception occurred."
    assert error.get_message_data() == {}


def test_it_keeps_internal_and_public_apart() -> None:
    error = AuthenticationError("internal detail", message_key="Public.", message_data={"n": 1})

    assert str(error) == "internal detail"
    assert error.get_message_key() == "Public."
    assert error.get_message_data() == {"n": 1}
