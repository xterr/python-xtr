"""The base error is what one ``except`` at the edge of an application catches."""

from __future__ import annotations

from xtr_serializer.exception import SerializerError


def test_it_is_an_exception() -> None:
    assert SerializerError.__mro__ == (SerializerError, Exception, BaseException, object)


def test_its_message_is_the_one_it_was_given() -> None:
    assert str(SerializerError("the value cannot be converted")) == "the value cannot be converted"


def test_it_never_renders_the_error_it_was_raised_from(secret: str) -> None:
    error = SerializerError("the value cannot be converted")
    error.__cause__ = ValueError(secret)

    assert secret not in str(error)
    assert secret not in repr(error)
