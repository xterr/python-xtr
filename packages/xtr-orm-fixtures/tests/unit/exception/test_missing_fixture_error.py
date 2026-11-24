"""Unit tests for :class:`xtr_orm_fixtures.exception.MissingFixtureError`."""

from __future__ import annotations

from xtr_orm_fixtures.exception import MissingFixtureError


def test_it_names_the_fixture_missing_and_the_one_depending_on_it() -> None:
    error = MissingFixtureError("Users", "Orders")

    assert (error.fixture, error.required_by) == ("Users", "Orders")
    assert str(error) == (
        'The fixture "Orders" depends on "Users", which was not added; '
        "add it, or remove the dependency."
    )


def test_it_is_a_lookup_error() -> None:
    assert isinstance(MissingFixtureError("Users", "Orders"), LookupError)
