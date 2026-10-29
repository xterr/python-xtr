"""Data that cannot become what was asked for is a serializer error, and a ``ValueError``."""

from __future__ import annotations

from xtr_serializer.exception import SerializerError, UnexpectedValueError


def test_it_is_a_serializer_error_and_a_value_error() -> None:
    assert UnexpectedValueError.__mro__ == (
        UnexpectedValueError,
        SerializerError,
        ValueError,
        Exception,
        BaseException,
        object,
    )


def test_its_message_is_the_one_it_was_given() -> None:
    assert str(UnexpectedValueError("the data does not fit the type")) == (
        "the data does not fit the type"
    )


def test_it_never_renders_the_error_it_was_raised_from(secret: str) -> None:
    error = UnexpectedValueError("the data does not fit the type")
    error.__cause__ = ValueError(secret)

    assert secret not in str(error)
    assert secret not in repr(error)
