"""Unit tests for :class:`xtr_orm_fixtures.exception.ReferenceNotFoundError`."""

from __future__ import annotations

from xtr_orm_fixtures.exception import ReferenceNotFoundError


def test_it_names_the_reference_and_its_class() -> None:
    error = ReferenceNotFoundError("admin", "User")

    assert (error.name, error.kind) == ("admin", "User")
    assert str(error) == 'No reference named "admin" was stored for "User".'


def test_it_is_a_lookup_error() -> None:
    assert isinstance(ReferenceNotFoundError("admin", "User"), LookupError)
