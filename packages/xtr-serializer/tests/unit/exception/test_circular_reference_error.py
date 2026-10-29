"""A value that contains itself is one of the serializer's errors, and a ``RuntimeError``."""

from __future__ import annotations

from xtr_serializer.exception import CircularReferenceError, SerializerError


def test_it_is_a_serializer_error_and_a_runtime_error() -> None:
    assert CircularReferenceError.__mro__ == (
        CircularReferenceError,
        SerializerError,
        RuntimeError,
        Exception,
        BaseException,
        object,
    )


def test_its_message_is_the_one_it_was_given() -> None:
    assert str(CircularReferenceError("the value contains itself")) == "the value contains itself"


def test_it_never_renders_the_error_it_was_raised_from(secret: str) -> None:
    error = CircularReferenceError("the value contains itself")
    error.__cause__ = ValueError(f"Circular reference detected: {secret}")

    assert secret not in str(error)
    assert secret not in repr(error)
