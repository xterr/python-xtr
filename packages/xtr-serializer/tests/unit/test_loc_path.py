"""A location is written as code addresses the data."""

from __future__ import annotations

import pytest

from xtr_serializer._loc_path import render_path


@pytest.mark.parametrize(
    ("keys", "expected"),
    [
        ((), None),
        (("price",), "price"),
        ((0,), "[0]"),
        (("items", 0, "price"), "items[0].price"),
        ((1, "a", 2, 3), "[1].a[2][3]"),
    ],
)
def test_it_joins_keys_and_indexes_into_a_path(
    keys: tuple[str | int, ...], expected: str | None
) -> None:
    assert render_path(keys) == expected
