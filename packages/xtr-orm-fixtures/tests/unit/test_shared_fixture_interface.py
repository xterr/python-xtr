"""Unit tests for :class:`xtr_orm_fixtures.SharedFixtureInterface`."""

from __future__ import annotations

from tests.support.contracts import NoLoad, Plain, Shared
from xtr_orm_fixtures import SharedFixtureInterface


def test_a_fixture_taking_the_run_s_references_shares_them() -> None:
    assert isinstance(Shared(), SharedFixtureInterface)


def test_a_plain_fixture_or_no_fixture_shares_nothing() -> None:
    assert not isinstance(Plain(), SharedFixtureInterface)
    assert not isinstance(NoLoad(), SharedFixtureInterface)
