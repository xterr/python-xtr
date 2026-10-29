"""Data that cannot become what was asked for is a serializer error, and a ``ValueError``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.round_trips import round_trips
from xtr_serializer.exception import SerializerError, UnexpectedValueError

if TYPE_CHECKING:
    from collections.abc import Callable


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


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = UnexpectedValueError("the data does not fit the type")

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is UnexpectedValueError
        assert restored.args == ("the data does not fit the type",)
        assert str(restored) == "the data does not fit the type"


def test_its_traceback_ends_with_its_message(
    traceback_of: Callable[[SerializerError], str],
) -> None:
    rendered = traceback_of(UnexpectedValueError("the data does not fit the type"))

    assert rendered.endswith("UnexpectedValueError: the data does not fit the type\n")
