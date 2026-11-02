"""A serializer put together wrongly is one of its errors, and a ``RuntimeError`` too."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.round_trips import round_trips
from xtr_serializer.exception import LogicError, SerializerError

if TYPE_CHECKING:
    from collections.abc import Callable


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


def test_it_survives_pickle_copy_and_deepcopy() -> None:
    error = LogicError("no normalizer can convert objects")

    restored_copies = round_trips(error)

    for restored in restored_copies:
        assert type(restored) is LogicError
        assert restored.args == ("no normalizer can convert objects",)
        assert str(restored) == "no normalizer can convert objects"


def test_its_traceback_ends_with_its_message(
    traceback_of: Callable[[SerializerError], str],
) -> None:
    rendered = traceback_of(LogicError("no normalizer can convert objects"))

    assert rendered.endswith("LogicError: no normalizer can convert objects\n")
