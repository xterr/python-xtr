from __future__ import annotations

from xtr_http_message import HttpMessageError, InvalidArgumentError


def test_it_carries_the_message_it_was_raised_with() -> None:
    assert str(InvalidArgumentError("Invalid port: 99999")) == "Invalid port: 99999"


def test_it_is_an_http_message_error() -> None:
    assert isinstance(InvalidArgumentError("x"), HttpMessageError)


def test_it_is_also_a_value_error() -> None:
    assert isinstance(InvalidArgumentError("x"), ValueError)
