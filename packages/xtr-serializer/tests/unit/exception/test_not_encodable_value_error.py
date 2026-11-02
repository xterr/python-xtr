"""Data with no form in the requested format is a value the serializer did not expect."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.round_trips import round_trips
from xtr_serializer.exception import NotEncodableValueError, SerializerError, UnexpectedValueError

if TYPE_CHECKING:
    from collections.abc import Callable


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


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = NotEncodableValueError("the text is not valid JSON")

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is NotEncodableValueError
        assert restored.args == ("the text is not valid JSON",)
        assert str(restored) == "the text is not valid JSON"


def test_its_traceback_ends_with_its_message(
    traceback_of: Callable[[SerializerError], str],
) -> None:
    rendered = traceback_of(NotEncodableValueError("the text is not valid JSON"))

    assert rendered.endswith("NotEncodableValueError: the text is not valid JSON\n")
