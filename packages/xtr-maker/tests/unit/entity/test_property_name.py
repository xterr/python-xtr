"""Unit tests for :class:`xtr_maker.entity.PropertyName`."""

from __future__ import annotations

import pytest

from xtr_maker import InvalidArgumentError
from xtr_maker.entity import PropertyName


def test_a_valid_name_is_returned_stripped() -> None:
    assert PropertyName.check(" title ") == "title"


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("1st", "not an identifier"),
        ("class", "keyword"),
        ("match", "keyword"),
        ("__secret", "name-mangled"),
        ("id", "base class already provides it"),
        ("created_at", "base class already provides it"),
        ("metadata", "base class already provides it"),
    ],
)
def test_a_name_no_attribute_can_have_is_refused(name: str, reason: str) -> None:
    with pytest.raises(InvalidArgumentError, match=reason):
        _ = PropertyName.check(name)
