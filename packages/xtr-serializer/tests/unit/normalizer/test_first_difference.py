"""Where a value and its copy first differ, in value or in exact type."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import pytest
from pydantic import BaseModel
from xtr_clock import DatePoint

from xtr_serializer.normalizer._first_difference import first_difference


class Line(BaseModel):
    price: int


def difference(value: object, read: object) -> tuple[type | None, list[str | int]]:
    steps: list[str | int] = []
    return first_difference(value, read, steps), steps


def at(kind: type, *steps: str | int) -> tuple[type, list[str | int]]:
    return kind, list(steps)


def test_equal_parts_of_the_same_types_have_no_difference() -> None:
    value: dict[object, object] = {"lines": [Line(price=1)], "tags": frozenset({"a"}), (1, 2): "p"}

    assert difference(value, {**value}) == (None, [])


@pytest.mark.parametrize(
    ("value", "read", "expected"),
    [
        pytest.param([1, True], [1, 1], at(bool, 1), id="item-type"),
        pytest.param([1, 2], [1], at(list), id="length"),
        pytest.param({"a": [1]}, {"a": [2]}, at(int, "a", 0), id="nested-value"),
        pytest.param({"a": 1}, {"b": 1}, at(dict), id="key"),
        pytest.param({"a": 1}, {"a": 1, "b": 2}, at(dict), id="key-count"),
        pytest.param({1: "a"}, {True: "a"}, at(dict), id="key-type"),
        pytest.param({2: (1,)}, {2: [1]}, at(tuple, 2), id="integer-key"),
        pytest.param({(1,): (1,)}, {(1,): [1]}, at(tuple), id="key-with-no-place"),
        pytest.param(
            Line.model_construct(price=True), Line(price=1), at(bool, "price"), id="model-field"
        ),
        pytest.param({frozenset({True})}, {frozenset({1})}, at(bool), id="set-member-type"),
        pytest.param({1}, {1, 2}, at(set), id="set-size"),
        pytest.param({1}, {2}, at(int), id="set-member"),
    ],
)
def test_it_finds_the_first_part_that_differs(
    value: object, read: object, expected: tuple[type, list[str | int]]
) -> None:
    assert difference(value, read) == expected


def test_a_datetime_subclass_may_come_back_as_a_datetime() -> None:
    at = datetime(2026, 1, 1, tzinfo=UTC)

    assert difference(DatePoint(2026, 1, 1, tzinfo=UTC), at) == (None, [])


def test_a_comparison_that_raises_leaves_the_steps_where_it_raised() -> None:
    steps: list[str | int] = []

    with pytest.raises(InvalidOperation):
        _ = first_difference({"a": [Decimal("sNaN")]}, {"a": [Decimal("sNaN")]}, steps)

    assert steps == ["a", 0]
