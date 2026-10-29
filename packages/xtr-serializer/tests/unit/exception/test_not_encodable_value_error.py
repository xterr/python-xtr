"""Data with no form in the requested format is a value the serializer did not expect."""

from __future__ import annotations

from xtr_serializer.exception import NotEncodableValueError, SerializerError, UnexpectedValueError


def test_it_is_an_unexpected_value() -> None:
    assert NotEncodableValueError.__mro__ == (
        NotEncodableValueError,
        UnexpectedValueError,
        SerializerError,
        ValueError,
        Exception,
        BaseException,
        object,
    )


def test_its_message_is_the_one_it_was_given() -> None:
    assert str(NotEncodableValueError("a float that is not a number has no JSON form")) == (
        "a float that is not a number has no JSON form"
    )


def test_it_never_renders_the_error_it_was_raised_from(secret: str) -> None:
    error = NotEncodableValueError("the text is not valid JSON")
    error.__cause__ = ValueError(f"expected value at line 1 column 1: {secret}")

    assert secret not in str(error)
    assert secret not in repr(error)
