"""Unit tests for :class:`xtr_orm_fixtures.Loader`."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, final, override

import pytest

from xtr_orm_fixtures import (
    DependentFixtureInterface,
    Fixture,
    FixtureGroupInterface,
    FixtureInterface,
    Loader,
    OrderedFixtureInterface,
)
from xtr_orm_fixtures.exception import (
    CircularReferenceError,
    InvalidArgumentError,
    MissingFixtureError,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


class Plain(Fixture):
    @override
    async def load(self, session: AsyncSession) -> None:
        del session


class A(Plain):
    pass


class B(Plain):
    pass


class C(Plain):
    pass


class First(Plain, OrderedFixtureInterface):
    @override
    def get_order(self) -> int:
        return 1


class Second(Plain, OrderedFixtureInterface):
    @override
    def get_order(self) -> int:
        return 2


class AlsoSecond(Plain, OrderedFixtureInterface):
    @override
    def get_order(self) -> int:
        return 2


class Depending(Plain, DependentFixtureInterface):
    """A fixture whose dependencies each test names."""

    dependencies: ClassVar[tuple[type[FixtureInterface], ...]] = ()

    @override
    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return type(self).dependencies


@final
class OnB(Depending):
    dependencies = (B,)


@final
class OnOnB(Depending):
    dependencies = (OnB,)


@final
class OnC(Depending):
    dependencies = (C,)


class Grouped(Plain, FixtureGroupInterface):
    @override
    @classmethod
    def get_groups(cls) -> Sequence[str]:
        return ("demo",)


@final
class GroupedOnB(Depending, FixtureGroupInterface):
    dependencies = (OnB,)

    @override
    @classmethod
    def get_groups(cls) -> Sequence[str]:
        return ("demo",)


def _classes(loader: Loader, groups: Sequence[str] = ()) -> list[type]:
    return [type(fixture) for fixture in loader.get_fixtures(groups)]


def _loader(*fixtures: FixtureInterface) -> Loader:
    loader = Loader()
    loader.add_fixtures(fixtures)
    return loader


def test_insertion_order_without_ordering() -> None:
    assert _classes(_loader(C(), A(), B())) == [C, A, B]


def test_a_class_is_added_once_the_first_instance_winning() -> None:
    first = A()

    loader = _loader(first, A())
    loader.add_fixture(A())

    assert loader.get_fixtures() == [first]


def test_ordered_fixtures_sort_by_order_and_come_first() -> None:
    loader = _loader(A(), Second(), AlsoSecond(), First())

    assert _classes(loader) == [First, Second, AlsoSecond, A]


def test_dependencies_load_before_dependents() -> None:
    loader = _loader(OnOnB(), OnB(), B())

    assert _classes(loader) == [B, OnB, OnOnB]


def test_independent_fixtures_keep_insertion_order() -> None:
    loader = _loader(OnB(), A(), B(), C())

    assert _classes(loader) == [A, B, C, OnB]


class OrderedAndDependent(Plain, OrderedFixtureInterface, DependentFixtureInterface):
    @override
    def get_order(self) -> int:
        return 1

    @override
    def get_dependencies(self) -> Sequence[type[FixtureInterface]]:
        return (A,)


def test_ordered_and_dependent_on_one_class_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        Loader().add_fixture(OrderedAndDependent())

    assert "both by a number and by its dependencies" in caught.value.reason


class OnItself(Depending):
    pass


OnItself.dependencies = (OnItself,)


class OnNothing(Depending):
    pass


def test_self_dependency_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        Loader().add_fixture(OnItself())

    assert caught.value.reason == "OnItself depends on itself"


def test_empty_dependencies_are_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        Loader().add_fixture(OnNothing())

    assert caught.value.reason == "OnNothing depends on nothing; drop get_dependencies"


def test_a_refused_fixture_leaves_none_of_its_batch_added() -> None:
    loader = Loader()

    with pytest.raises(InvalidArgumentError):
        loader.add_fixtures([A(), OnNothing()])

    assert loader.get_fixtures() == []


def test_missing_dependency_raises() -> None:
    with pytest.raises(MissingFixtureError) as caught:
        _ = _loader(OnB()).get_fixtures()

    assert (caught.value.fixture, caught.value.required_by) == ("B", "OnB")


class Ping(Depending):
    pass


class Pong(Depending):
    pass


Ping.dependencies = (Pong,)
Pong.dependencies = (Ping,)


def test_cycle_raises_naming_the_classes() -> None:
    with pytest.raises(CircularReferenceError) as caught:
        _ = _loader(Ping(), Pong()).get_fixtures()

    fixtures = caught.value.fixtures
    assert set(fixtures) == {"Ping", "Pong"}
    assert fixtures[0] == fixtures[-1]


def test_a_dependency_on_an_ordered_fixture_is_met_by_its_number() -> None:
    @final
    class OnFirst(Depending):
        dependencies = (First,)

    assert _classes(_loader(OnFirst(), First())) == [First, OnFirst]


def test_group_selects_its_fixtures_and_their_dependencies() -> None:
    loader = _loader(A(), GroupedOnB(), OnB(), B(), Grouped(), C())

    assert _classes(loader, ["demo"]) == [B, Grouped, OnB, GroupedOnB]


def test_a_dependency_of_two_selected_fixtures_is_selected_once() -> None:
    loader = _loader(OnB(), OnOnB(), B(), A())

    assert _classes(loader, ["OnB", "OnOnB"]) == [B, OnB, OnOnB]


def test_class_name_is_an_implicit_group() -> None:
    loader = _loader(A(), OnC(), C())

    assert _classes(loader, ["OnC"]) == [C, OnC]


def test_unknown_group_selects_nothing() -> None:
    assert _classes(_loader(A(), Grouped()), ["nowhere"]) == []


def test_load_from_package_skips_abstract_and_imported_classes() -> None:
    loader = Loader()

    loader.load_from_package("tests.fixtures.app_fixtures")

    # Added module by module, in name order — shop.orders before users — then ordered.
    names = [type(fixture).__qualname__ for fixture in loader.get_fixtures()]
    assert names == ["UserFixtures", "AdminFixtures", "OrderFixtures"]


def test_load_from_a_plain_module_takes_its_fixtures_alone() -> None:
    loader = Loader()

    loader.load_from_package("tests.fixtures.app_fixtures.users")

    assert [type(fixture).__qualname__ for fixture in loader.get_fixtures()] == [
        "UserFixtures",
        "AdminFixtures",
    ]
