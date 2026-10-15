"""The too-many-attempts error says how long the caller must wait."""

from __future__ import annotations

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
