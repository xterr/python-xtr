"""The JSON envelope a session keeps the last authentication error in, and the error rebuilt."""

from __future__ import annotations

import json
import sys
from typing import ClassVar, final

import pytest
from xtr_security_core.exception import (
    AuthenticationError,
    BadCredentialsError,
    DisabledError,
    TooManyLoginAttemptsAuthenticationError,
)
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.exception import InvalidCsrfTokenError
from xtr_security_http.session.authentication_error_serializer import (
    authentication_error_from_session,
    authentication_error_to_session,
)


@final
class _ApplicationError(AuthenticationError):
    """An error class of the application's own."""

    MESSAGE_KEY: ClassVar[str] = "Your subscription has lapsed."


def test_an_error_is_kept_as_an_envelope_of_its_kind_and_public_half() -> None:
    error = BadCredentialsError("the password of ada did not match")

    assert authentication_error_to_session(error) == {
        "v": 1,
        "kind": "xtr_security_core.exception.bad_credentials_error:BadCredentialsError",
        "message_key": "Invalid credentials.",
        "message_data": {},
    }


def test_the_envelope_holds_json_and_never_the_internal_message() -> None:
    error = DisabledError(InMemoryUser("ada"), "ada was disabled by an administrator")

    envelope = authentication_error_to_session(error)

    assert json.loads(json.dumps(envelope)) == envelope
    assert "administrator" not in json.dumps(envelope)


@pytest.mark.parametrize(
    "error",
    [
        BadCredentialsError("internal"),
        DisabledError(InMemoryUser("ada")),
        InvalidCsrfTokenError("internal"),
        _ApplicationError("internal"),
    ],
    ids=["bad-credentials", "disabled", "invalid-csrf-token", "application-error"],
)
def test_an_error_is_rebuilt_as_its_own_class_with_its_key(error: AuthenticationError) -> None:
    rebuilt = authentication_error_from_session(authentication_error_to_session(error))

    assert type(rebuilt) is type(error)
    assert rebuilt is not None
    assert rebuilt.get_message_key() == error.get_message_key()
    assert str(rebuilt) == error.get_message_key()


def test_an_error_is_rebuilt_with_the_data_it_kept() -> None:
    kept = authentication_error_to_session(TooManyLoginAttemptsAuthenticationError(3))

    rebuilt = authentication_error_from_session(kept)

    assert isinstance(rebuilt, TooManyLoginAttemptsAuthenticationError)
    assert rebuilt.threshold == 3
    assert rebuilt.get_message_data() == {"%minutes%": 3, "%count%": 3}


def test_a_kind_no_loaded_class_answers_to_is_rebuilt_as_a_plain_error() -> None:
    envelope = {
        **authentication_error_to_session(BadCredentialsError()),
        "kind": "xtr_never_loaded_module:LostError",
    }

    rebuilt = authentication_error_from_session(envelope)

    assert type(rebuilt) is AuthenticationError
    assert rebuilt is not None
    assert rebuilt.get_message_key() == "Invalid credentials."
    assert "xtr_never_loaded_module" not in sys.modules


@pytest.mark.parametrize(
    "value",
    [
        None,
        "Invalid credentials.",
        BadCredentialsError("live"),
        {"v": 2, "kind": "k", "message_key": "Invalid credentials.", "message_data": {}},
        {"v": 1, "kind": 1, "message_key": "Invalid credentials.", "message_data": {}},
        {"v": 1, "kind": "k", "message_key": None, "message_data": {}},
        {"v": 1, "kind": "k", "message_key": "Invalid credentials.", "message_data": []},
        {"v": 1, "kind": "k", "message_key": "Invalid credentials.", "message_data": {1: "a"}},
    ],
    ids=[
        "none",
        "string",
        "live-error",
        "another-version",
        "kind-no-string",
        "key-no-string",
        "data-no-object",
        "data-keyed-by-no-string",
    ],
)
def test_a_value_that_is_no_envelope_is_no_error(value: object) -> None:
    assert authentication_error_from_session(value) is None
