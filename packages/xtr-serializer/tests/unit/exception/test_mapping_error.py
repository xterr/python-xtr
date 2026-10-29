"""A class hierarchy registered wrongly is a logic error: the code is at fault, not the data."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.round_trips import round_trips
from xtr_serializer.exception import LogicError, MappingError, SerializerError

if TYPE_CHECKING:
    from collections.abc import Callable


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


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = MappingError("the name 'delivery' is already registered")

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is MappingError
        assert restored.args == ("the name 'delivery' is already registered",)
        assert str(restored) == "the name 'delivery' is already registered"


def test_its_traceback_ends_with_its_message(
    traceback_of: Callable[[SerializerError], str],
) -> None:
    rendered = traceback_of(MappingError("the name 'delivery' is already registered"))

    assert rendered.endswith("MappingError: the name 'delivery' is already registered\n")
