"""Refusals met inside a value of a hierarchy, kept until it is written rather than raised there."""

from __future__ import annotations

import pytest
from pydantic_core import PydanticSerializationUnexpectedValue

from xtr_serializer.mapping._deferred_refusals import (
    deferring_refusals,
    refused_or_deferred,
    written_or_deferred,
)


def refuse(value: object) -> object:
    raise ValueError(value)


def refuse_strictly(value: object) -> object:
    raise PydanticSerializationUnexpectedValue(str(value))


def test_a_value_is_written_as_it_is() -> None:
    with deferring_refusals() as deferred:
        assert written_or_deferred(1, str) == "1"

    assert deferred == []


def test_a_refusal_is_raised_unless_refusals_are_kept() -> None:
    with pytest.raises(ValueError, match="one"):
        _ = written_or_deferred("one", refuse)


def test_a_refusal_is_kept_in_order_and_an_empty_object_written_instead() -> None:
    with deferring_refusals() as deferred:
        written = [written_or_deferred(name, refuse) for name in ("one", "two")]

    assert written == [{}, {}]
    assert [str(error) for error in deferred] == ["one", "two"]


def test_refusals_kept_inside_are_kept_apart_and_none_after() -> None:
    with deferring_refusals() as outer:
        with deferring_refusals() as inner:
            _ = written_or_deferred("inner", refuse)
        _ = written_or_deferred("outer", refuse)

    assert ([str(error) for error in inner], [str(error) for error in outer]) == (
        ["inner"],
        ["outer"],
    )
    with pytest.raises(ValueError, match="after"):
        _ = written_or_deferred("after", refuse)


def test_a_value_refused_on_a_first_strict_try_is_let_through_to_the_next() -> None:
    value = object()
    with deferring_refusals() as deferred:
        with pytest.raises(PydanticSerializationUnexpectedValue):
            _ = written_or_deferred(value, refuse_strictly)
        written = written_or_deferred(value, lambda _: "written")
        with pytest.raises(PydanticSerializationUnexpectedValue):
            _ = written_or_deferred(value, refuse_strictly)

    assert written == "written"
    assert deferred == []


def test_a_value_refused_on_both_tries_is_kept() -> None:
    value = object()
    with deferring_refusals() as deferred:
        with pytest.raises(PydanticSerializationUnexpectedValue):
            _ = written_or_deferred(value, refuse_strictly)
        written = written_or_deferred(value, refuse_strictly)

    assert written == {}
    assert [type(error) for error in deferred] == [PydanticSerializationUnexpectedValue]


def test_a_refusal_given_is_raised_unless_refusals_are_kept() -> None:
    with pytest.raises(ValueError, match="given"):
        _ = refused_or_deferred(ValueError("given"))


def test_a_refusal_given_is_kept_while_refusals_are() -> None:
    error = ValueError("given")
    with deferring_refusals() as deferred:
        written = refused_or_deferred(error)

    assert (written, deferred) == ({}, [error])
