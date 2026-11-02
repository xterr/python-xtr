"""An argument the serializer cannot use is one of its errors, and a ``ValueError`` too."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.round_trips import round_trips
from xtr_serializer.exception import InvalidArgumentError, SerializerError

if TYPE_CHECKING:
    from collections.abc import Callable


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


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = InvalidArgumentError("a serializer name cannot be empty")

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is InvalidArgumentError
        assert restored.args == ("a serializer name cannot be empty",)
        assert str(restored) == "a serializer name cannot be empty"


def test_its_traceback_ends_with_its_message(
    traceback_of: Callable[[SerializerError], str],
) -> None:
    rendered = traceback_of(InvalidArgumentError("a serializer name cannot be empty"))

    assert rendered.endswith("InvalidArgumentError: a serializer name cannot be empty\n")
