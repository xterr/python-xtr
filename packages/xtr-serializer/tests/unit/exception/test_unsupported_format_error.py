"""A format nothing reads or writes is named in the error, quoted so it cannot forge a line."""

from __future__ import annotations

from xtr_serializer.exception import (
    NotEncodableValueError,
    SerializerError,
    UnexpectedValueError,
    UnsupportedFormatError,
)


def test_it_is_a_value_that_cannot_be_encoded() -> None:
    assert UnsupportedFormatError.__mro__ == (
        UnsupportedFormatError,
        NotEncodableValueError,
        UnexpectedValueError,
        SerializerError,
        ValueError,
        Exception,
        BaseException,
        object,
    )


def test_it_keeps_the_format_asked_for() -> None:
    assert UnsupportedFormatError("xml").format == "xml"


def test_its_message_names_the_format() -> None:
    assert str(UnsupportedFormatError("xml")) == "the format 'xml' is not supported"


def test_a_format_cannot_break_its_message_across_lines() -> None:
    assert str(UnsupportedFormatError("xml\nforged")) == (
        "the format 'xml\\nforged' is not supported"
    )


def test_it_never_renders_the_error_it_was_raised_from(secret: str) -> None:
    error = UnsupportedFormatError("xml")
    error.__cause__ = ValueError(secret)

    assert secret not in str(error)
    assert secret not in repr(error)
