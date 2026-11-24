"""Unit tests for :class:`xtr_orm_fixtures.exception.CircularReferenceError`."""

from __future__ import annotations

from xtr_orm_fixtures.exception import CircularReferenceError


def test_it_names_the_fixtures_in_the_circle_in_order() -> None:
    error = CircularReferenceError(("Users", "Orders", "Users"))

    assert error.fixtures == ("Users", "Orders", "Users")
    assert str(error) == "The fixtures depend on one another in a circle: Users -> Orders -> Users."
