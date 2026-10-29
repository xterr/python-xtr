"""A format nothing reads or writes is named in the error, quoted so it cannot forge a line."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.round_trips import round_trips
from xtr_serializer.exception import (
    NotEncodableValueError,
    SerializerError,
    UnexpectedValueError,
    UnsupportedFormatError,
)

if TYPE_CHECKING:
    from collections.abc import Callable


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


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = UnsupportedFormatError("xml")

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is UnsupportedFormatError
        assert restored.args == ("the format 'xml' is not supported",)
        assert str(restored) == "the format 'xml' is not supported"
        assert restored.format == "xml"


def test_its_traceback_names_the_format(
    traceback_of: Callable[[SerializerError], str],
) -> None:
    rendered = traceback_of(UnsupportedFormatError("xml"))

    assert rendered.endswith("UnsupportedFormatError: the format 'xml' is not supported\n")
