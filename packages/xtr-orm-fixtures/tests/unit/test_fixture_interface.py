"""Unit tests for :class:`xtr_orm_fixtures.FixtureInterface`."""

from __future__ import annotations

from tests.support.contracts import NoLoad, Plain
from xtr_orm_fixtures import FixtureInterface


def test_a_class_loading_into_a_session_is_a_fixture() -> None:
    assert isinstance(Plain(), FixtureInterface)


def test_a_class_that_does_not_load_is_no_fixture() -> None:
    assert not isinstance(NoLoad(), FixtureInterface)
