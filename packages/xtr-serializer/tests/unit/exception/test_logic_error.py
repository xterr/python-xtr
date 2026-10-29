"""A serializer put together wrongly is one of its errors, and a ``RuntimeError`` too."""

from __future__ import annotations

from xtr_serializer.exception import LogicError, SerializerError


def test_it_is_a_serializer_error_and_a_runtime_error() -> None:
    assert LogicError.__mro__ == (
        LogicError,
        SerializerError,
        RuntimeError,
        Exception,
        BaseException,
        object,
    )


def test_its_message_is_the_one_it_was_given() -> None:
    assert str(LogicError("no normalizer can convert objects")) == (
        "no normalizer can convert objects"
    )


def test_it_never_renders_the_error_it_was_raised_from(secret: str) -> None:
    error = LogicError("no normalizer can convert objects")
    error.__cause__ = ValueError(secret)

    assert secret not in str(error)
    assert secret not in repr(error)
