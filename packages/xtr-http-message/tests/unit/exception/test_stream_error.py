from __future__ import annotations

from xtr_http_message import HttpMessageError, StreamError


def test_it_carries_the_message_it_was_raised_with() -> None:
    assert str(StreamError("Stream is detached")) == "Stream is detached"


def test_it_is_an_http_message_error() -> None:
    assert isinstance(StreamError("x"), HttpMessageError)


def test_it_is_also_a_runtime_error() -> None:
    assert isinstance(StreamError("x"), RuntimeError)
