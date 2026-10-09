from __future__ import annotations

from xtr_http_message import HttpMessageError


def test_it_is_an_exception() -> None:
    assert issubclass(HttpMessageError, Exception)


def test_it_carries_the_message_it_was_raised_with() -> None:
    assert str(HttpMessageError("what went wrong")) == "what went wrong"
