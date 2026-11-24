"""Unit tests for :class:`xtr_orm_fixtures.FixtureGroupInterface`."""

from __future__ import annotations

from tests.support.contracts import Grouped, NoLoad, Plain
from xtr_orm_fixtures import FixtureGroupInterface


def test_a_fixture_naming_its_groups_belongs_to_them() -> None:
    assert isinstance(Grouped(), FixtureGroupInterface)
    assert tuple(Grouped.get_groups()) == ("demo",)


def test_a_plain_fixture_or_no_fixture_names_no_group() -> None:
    assert not isinstance(Plain(), FixtureGroupInterface)
    assert not isinstance(NoLoad(), FixtureGroupInterface)
