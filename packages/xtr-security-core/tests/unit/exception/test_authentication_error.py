"""The authentication base error keeps its internal and public text apart."""

from __future__ import annotations

import pytest

from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
    CustomUserMessageAuthenticationError,
    DisabledError,
    InsufficientAuthenticationError,
    SecurityError,
)


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


def test_a_session_keeps_the_public_half_and_never_the_internal_message() -> None:
    error = AuthenticationError(
        "the password of ada did not match",
        message_key="Public.",
        message_data={"%count%": 3},
    )

    assert error.to_session() == {"message_key": "Public.", "message_data": {"%count%": 3}}


def test_a_session_keeps_only_the_data_json_gives_back_as_it_was() -> None:
    error = AuthenticationError(
        message_key="Public.",
        message_data={
            "%name%": "ada",
            "%tuple%": ("a", "b"),
            "%object%": object(),
            "%nan%": float("nan"),
            "%nested%": {"list": [1, 2.5, None, True]},
        },
    )

    assert error.to_session()["message_data"] == {
        "%name%": "ada",
        "%nested%": {"list": [1, 2.5, None, True]},
    }


def test_it_is_rebuilt_from_a_session_with_its_key_and_data() -> None:
    rebuilt = AuthenticationError.from_session("Public.", {"%count%": 3})

    assert type(rebuilt) is AuthenticationError
    assert rebuilt.get_message_key() == "Public."
    assert rebuilt.get_message_data() == {"%count%": 3}


def test_a_rebuilt_errors_internal_message_is_its_key() -> None:
    rebuilt = AuthenticationError.from_session("Public.", {})

    assert str(rebuilt) == "Public."


@pytest.mark.parametrize(
    "error_class",
    [
        BadCredentialsError,
        DisabledError,
        InsufficientAuthenticationError,
        CustomUserMessageAuthenticationError,
    ],
)
def test_a_subclass_is_rebuilt_from_a_session_as_its_own_class(
    error_class: type[AuthenticationError],
) -> None:
    rebuilt = error_class.from_session("Kept.", {"%n%": 1})

    assert type(rebuilt) is error_class
    assert rebuilt.get_message_key() == "Kept."
    assert rebuilt.get_message_data() == {"%n%": 1}
    assert str(rebuilt) == "Kept."
