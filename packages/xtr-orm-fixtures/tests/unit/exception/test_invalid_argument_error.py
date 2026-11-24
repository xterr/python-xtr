"""Unit tests for :class:`xtr_orm_fixtures.exception.InvalidArgumentError`."""

from __future__ import annotations

from xtr_orm_fixtures.exception import InvalidArgumentError


def test_it_is_a_value_error_carrying_its_reason() -> None:
    error = InvalidArgumentError("bad")

    assert isinstance(error, ValueError)
    assert error.reason == "bad"
    assert str(error) == "bad"
