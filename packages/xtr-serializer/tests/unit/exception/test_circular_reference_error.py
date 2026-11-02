"""A value that contains itself is one of the serializer's errors, and a ``RuntimeError``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.round_trips import round_trips
from xtr_serializer.exception import CircularReferenceError, SerializerError

if TYPE_CHECKING:
    from collections.abc import Callable


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


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = CircularReferenceError("the value contains itself")

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is CircularReferenceError
        assert restored.args == ("the value contains itself",)
        assert str(restored) == "the value contains itself"


def test_its_traceback_ends_with_its_message(
    traceback_of: Callable[[SerializerError], str],
) -> None:
    rendered = traceback_of(CircularReferenceError("the value contains itself"))

    assert rendered.endswith("CircularReferenceError: the value contains itself\n")
