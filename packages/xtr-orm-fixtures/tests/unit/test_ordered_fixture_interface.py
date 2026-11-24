"""Unit tests for :class:`xtr_orm_fixtures.OrderedFixtureInterface`."""

from __future__ import annotations

from tests.support.contracts import NoLoad, Ordered, Plain
from xtr_orm_fixtures import OrderedFixtureInterface


def test_a_fixture_giving_a_number_is_ordered_by_it() -> None:
    assert isinstance(Ordered(), OrderedFixtureInterface)


def test_a_plain_fixture_or_no_fixture_is_not_ordered() -> None:
    assert not isinstance(Plain(), OrderedFixtureInterface)
    assert not isinstance(NoLoad(), OrderedFixtureInterface)
