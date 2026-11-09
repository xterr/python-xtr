"""The too-many-attempts error says how long the caller must wait."""

from __future__ import annotations

import pytest

from xtr_security_core.exception import (
    AuthenticationError,
    SecurityError,
    TooManyLoginAttemptsAuthenticationError,
)


def test_it_is_an_authentication_error() -> None:
    assert isinstance(TooManyLoginAttemptsAuthenticationError(), AuthenticationError)
    assert issubclass(TooManyLoginAttemptsAuthenticationError, SecurityError)


def test_without_a_threshold_it_says_later() -> None:
    error = TooManyLoginAttemptsAuthenticationError()

    assert error.get_message_key() == "Too many failed login attempts, please try again later."
    assert error.get_message_data() == {"%minutes%": None, "%count%": 0}
    assert error.threshold is None


def test_with_one_minute_it_says_one_minute() -> None:
    error = TooManyLoginAttemptsAuthenticationError(1)

    assert error.get_message_key() == (
        "Too many failed login attempts, please try again in %minutes% minute."
    )
    assert error.get_message_data() == {"%minutes%": 1, "%count%": 1}
    assert error.threshold == 1


def test_with_several_minutes_it_says_minutes() -> None:
    error = TooManyLoginAttemptsAuthenticationError(5)

    assert error.get_message_key() == (
        "Too many failed login attempts, please try again in %minutes% minutes."
    )
    assert error.get_message_data() == {"%minutes%": 5, "%count%": 5}
    assert error.threshold == 5


def test_it_is_rebuilt_from_a_session_with_the_wait_it_named() -> None:
    error = TooManyLoginAttemptsAuthenticationError(5)

    rebuilt = TooManyLoginAttemptsAuthenticationError.from_session(
        error.get_message_key(),
        error.get_message_data(),
    )

    assert type(rebuilt) is TooManyLoginAttemptsAuthenticationError
    assert rebuilt.threshold == 5
    assert rebuilt.get_message_key() == (
        "Too many failed login attempts, please try again in %minutes% minutes."
    )
    assert rebuilt.get_message_data() == {"%minutes%": 5, "%count%": 5}


@pytest.mark.parametrize("minutes", [None, "5", True])
def test_a_wait_the_session_kept_no_count_of_is_rebuilt_unquantified(minutes: object) -> None:
    rebuilt = TooManyLoginAttemptsAuthenticationError.from_session(
        "Too many failed login attempts, please try again later.",
        {"%minutes%": minutes, "%count%": 0},
    )

    assert rebuilt.threshold is None
