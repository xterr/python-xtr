"""Unit tests for :class:`xtr_maker.entity.FieldType`."""

from __future__ import annotations

import pytest

from xtr_maker.entity import FieldType


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("published_at", FieldType.DATETIME),
        ("author_id", FieldType.UUID),
        ("is_active", FieldType.BOOLEAN),
        ("has_stock", FieldType.BOOLEAN),
        ("title", FieldType.STRING),
    ],
)
def test_a_name_suggests_its_type(name: str, expected: FieldType) -> None:
    assert FieldType.guess(name) is expected


def test_the_types_are_named_as_typed() -> None:
    assert FieldType("big_integer") is FieldType.BIG_INTEGER
