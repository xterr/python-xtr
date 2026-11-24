"""Unit tests for :class:`xtr_orm_fixtures.Fixture`."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

import pytest

from tests.support.models import User
from xtr_orm_fixtures import Fixture, ReferenceRepository, SharedFixtureInterface
from xtr_orm_fixtures.exception import InvalidArgumentError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class UserFixtures(Fixture):
    @override
    async def load(self, session: AsyncSession) -> None:
        del session


def test_fixture_without_repository_raises() -> None:
    fixture = UserFixtures()

    with pytest.raises(InvalidArgumentError) as caught:
        fixture.add_reference("admin", User(name="ada"))

    assert caught.value.reason.startswith("UserFixtures has no references yet")
    with pytest.raises(InvalidArgumentError):
        _ = fixture.has_reference("admin", User)


def test_fixture_delegates_to_its_repository() -> None:
    repository = ReferenceRepository()
    fixture = UserFixtures()
    fixture.set_reference_repository(repository)
    ada, bob = User(name="ada"), User(name="bob")

    fixture.add_reference("admin", ada)
    fixture.set_reference("first", bob)

    assert repository.get_reference("admin", User) is ada
    assert fixture.get_reference("first", User) is bob
    assert fixture.has_reference("admin", User)


def test_a_fixture_shares_references() -> None:
    assert isinstance(UserFixtures(), SharedFixtureInterface)


def test_fixtures_hold_their_own_repository() -> None:
    first, second = UserFixtures(), UserFixtures()

    first.set_reference_repository(ReferenceRepository())

    with pytest.raises(InvalidArgumentError):
        _ = second.has_reference("admin", User)
