"""Unit tests for :class:`xtr_orm_fixtures.DependentFixtureInterface`."""

from __future__ import annotations

from tests.support.contracts import Dependent, NoLoad, Plain
from xtr_orm_fixtures import DependentFixtureInterface


def test_a_fixture_naming_its_dependencies_depends_on_them() -> None:
    assert isinstance(Dependent(), DependentFixtureInterface)


def test_a_plain_fixture_or_no_fixture_depends_on_nothing() -> None:
    assert not isinstance(Plain(), DependentFixtureInterface)
    assert not isinstance(NoLoad(), DependentFixtureInterface)
