"""The base error is what one ``except`` at the edge of an application catches."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.round_trips import round_trips
from xtr_serializer.exception import SerializerError

if TYPE_CHECKING:
    from collections.abc import Callable


def test_it_is_an_exception() -> None:
    assert SerializerError.__mro__ == (SerializerError, Exception, BaseException, object)


def test_its_message_is_the_one_it_was_given() -> None:
    assert str(SerializerError("the value cannot be converted")) == "the value cannot be converted"


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = SerializerError("the value cannot be converted")

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is SerializerError
        assert restored.args == ("the value cannot be converted",)
        assert str(restored) == "the value cannot be converted"


def test_its_traceback_ends_with_its_message(
    traceback_of: Callable[[SerializerError], str],
) -> None:
    rendered = traceback_of(SerializerError("the value cannot be converted"))

    assert rendered.endswith("SerializerError: the value cannot be converted\n")
