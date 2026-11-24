"""Unit tests for :class:`xtr_orm_fixtures.exception.ReferenceExistsError`."""

from __future__ import annotations

from xtr_orm_fixtures.exception import ReferenceExistsError


def test_it_names_the_reference_and_says_how_to_replace_it() -> None:
    error = ReferenceExistsError("admin", "User")

    assert (error.name, error.kind) == ("admin", "User")
    assert str(error) == (
        'A reference named "admin" is already stored for "User"; use set_reference to replace it.'
    )
