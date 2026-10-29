"""A class hierarchy registered wrongly is a logic error: the code is at fault, not the data."""

from __future__ import annotations

from xtr_serializer.exception import LogicError, MappingError, SerializerError


def test_it_is_a_logic_error() -> None:
    assert MappingError.__mro__ == (
        MappingError,
        LogicError,
        SerializerError,
        RuntimeError,
        Exception,
        BaseException,
        object,
    )


def test_its_message_is_the_one_it_was_given() -> None:
    assert str(MappingError("the name 'delivery' is already registered")) == (
        "the name 'delivery' is already registered"
    )


def test_it_never_renders_the_error_it_was_raised_from(secret: str) -> None:
    error = MappingError("the name 'delivery' is already registered")
    error.__cause__ = ValueError(secret)

    assert secret not in str(error)
    assert secret not in repr(error)
