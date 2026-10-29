"""An argument the serializer cannot use is one of its errors, and a ``ValueError`` too."""

from __future__ import annotations

from xtr_serializer.exception import InvalidArgumentError, SerializerError


def test_it_is_a_serializer_error_and_a_value_error() -> None:
    assert InvalidArgumentError.__mro__ == (
        InvalidArgumentError,
        SerializerError,
        ValueError,
        Exception,
        BaseException,
        object,
    )


def test_its_message_is_the_one_it_was_given() -> None:
    assert str(InvalidArgumentError("a serializer name cannot be empty")) == (
        "a serializer name cannot be empty"
    )


def test_it_never_renders_the_error_it_was_raised_from(secret: str) -> None:
    error = InvalidArgumentError("a serializer name cannot be empty")
    error.__cause__ = ValueError(secret)

    assert secret not in str(error)
    assert secret not in repr(error)
