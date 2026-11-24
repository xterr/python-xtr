"""The fixtures of a run, and the order they load in."""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from graphlib import CycleError, TopologicalSorter
from typing import TYPE_CHECKING, cast, final

from .dependent_fixture_interface import DependentFixtureInterface
from .exception import CircularReferenceError, InvalidArgumentError, MissingFixtureError
from .fixture_group_interface import FixtureGroupInterface
from .fixture_interface import FixtureInterface
from .ordered_fixture_interface import OrderedFixtureInterface

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Sequence
    from types import ModuleType

__all__ = ["Loader"]


@final
class Loader:
    """Collects the fixtures of a run, one per class, and orders them.

    Numbered fixtures load first, by their number; the others after, each
    after the fixtures it depends on. Fixtures nothing else orders keep the
    order they were added in. A run may load only some groups: each fixture
    is in the groups it names and in the one named after its class, and a
    fixture selected brings the fixtures it depends on along.
    """

    __slots__ = ("_fixtures",)

    def __init__(self) -> None:
        """Start with no fixtures."""
        self._fixtures: dict[type, FixtureInterface] = {}

    def add_fixture(self, fixture: FixtureInterface) -> None:
        """Add ``fixture``, unless a fixture of its class was added already.

        Raises:
            InvalidArgumentError: If it is both numbered and dependent, or its
                dependencies are empty or name its own class.
        """
        _check(fixture)
        _ = self._fixtures.setdefault(type(fixture), fixture)

    def add_fixtures(self, fixtures: Iterable[FixtureInterface]) -> None:
        """Add each of ``fixtures``, all or none: each is checked before any is added.

        Raises:
            InvalidArgumentError: If one of them is refused; then none is added.
        """
        listed = list(fixtures)
        for fixture in listed:
            _check(fixture)
        for fixture in listed:
            _ = self._fixtures.setdefault(type(fixture), fixture)

    def get_fixtures(self, groups: Sequence[str] = ()) -> list[FixtureInterface]:
        """Return the fixtures in the order they load; only those of ``groups``, if any named.

        Raises:
            MissingFixtureError: If a fixture depends on one that was not added.
            CircularReferenceError: If fixtures depend on one another in a circle.
        """
        ordered = self._ordered()
        if not groups:
            return ordered
        wanted = self._selected(frozenset(groups))
        return [fixture for fixture in ordered if type(fixture) in wanted]

    def load_from_package(self, name: str) -> None:
        """Add a fixture of every concrete fixture class the modules of package ``name`` define.

        For use without a container: each class is built with no arguments.
        A class a module only imports belongs to the module defining it, and
        an abstract one is no fixture.
        """
        for module in _modules_of(importlib.import_module(name)):
            self.add_fixtures(cls() for cls in _fixture_classes_of(module))

    def _ordered(self) -> list[FixtureInterface]:
        numbered = [f for f in self._fixtures.values() if isinstance(f, OrderedFixtureInterface)]
        numbered.sort(key=lambda fixture: fixture.get_order())
        rest = [f for f in self._fixtures.values() if not isinstance(f, OrderedFixtureInterface)]
        position: dict[type, int] = {type(fixture): index for index, fixture in enumerate(rest)}
        graph: TopologicalSorter[type] = TopologicalSorter()
        for fixture in rest:
            graph.add(
                type(fixture), *(dep for dep in self._dependencies(fixture) if dep in position)
            )
        try:
            graph.prepare()
        except CycleError as error:
            cycle = cast("list[type]", error.args[1])
            raise CircularReferenceError(tuple(cls.__qualname__ for cls in cycle)) from error
        loaded: list[FixtureInterface] = list(numbered)
        while graph.is_active():
            ready: list[type] = sorted(graph.get_ready(), key=lambda cls: position[cls])
            loaded.extend(self._fixtures[cls] for cls in ready)
            graph.done(*ready)
        return loaded

    def _dependencies(self, fixture: FixtureInterface) -> list[type]:
        """Return the classes ``fixture`` depends on, each of them added.

        Raises:
            MissingFixtureError: If one was not added.
        """
        if not isinstance(fixture, DependentFixtureInterface):
            return []
        dependencies: list[type] = list(fixture.get_dependencies())
        for dependency in dependencies:
            if dependency not in self._fixtures:
                raise MissingFixtureError(dependency.__qualname__, type(fixture).__qualname__)
        return dependencies

    def _selected(self, groups: frozenset[str]) -> set[type]:
        """Return the classes in ``groups``, with every fixture they depend on, transitively."""
        selected = {cls for cls in self._fixtures if groups & _groups_of(cls)}
        pending = list(selected)
        while pending:
            for dependency in self._dependencies(self._fixtures[pending.pop()]):
                if dependency not in selected:
                    selected.add(dependency)
                    pending.append(dependency)
        return selected


def _check(fixture: FixtureInterface) -> None:
    """Refuse a fixture its run could not place.

    Raises:
        InvalidArgumentError: If it is both numbered and dependent, or its
            dependencies are empty or name its own class.
    """
    if not isinstance(fixture, DependentFixtureInterface):
        return
    name = type(fixture).__qualname__
    if isinstance(fixture, OrderedFixtureInterface):
        raise InvalidArgumentError(
            f"{name} is ordered both by a number and by its dependencies; keep one of them"
        )
    dependencies = list(fixture.get_dependencies())
    if not dependencies:
        raise InvalidArgumentError(f"{name} depends on nothing; drop get_dependencies")
    if type(fixture) in dependencies:
        raise InvalidArgumentError(f"{name} depends on itself")


def _groups_of(cls: type) -> frozenset[str]:
    """Return the groups of the fixture class ``cls``: those it names, and its own name."""
    named = cls.get_groups() if issubclass(cls, FixtureGroupInterface) else ()
    return frozenset((*named, cls.__name__))


def _modules_of(package: ModuleType) -> Iterator[ModuleType]:
    """Yield ``package`` and every module under it, in name order."""
    yield package
    # Read where the import system sets it: a module ``__getattr__`` may answer any name.
    path = cast("Sequence[str] | None", vars(package).get("__path__"))
    if path is None:
        return
    found = sorted(pkgutil.walk_packages(path, f"{package.__name__}."), key=lambda m: m.name)
    for module in found:
        yield importlib.import_module(module.name)


def _fixture_classes_of(module: ModuleType) -> list[type[FixtureInterface]]:
    """Return the concrete fixture classes ``module`` defines, in the order it defines them."""
    return [
        value
        for value in cast("dict[str, object]", vars(module)).values()
        if inspect.isclass(value)
        and value.__module__ == module.__name__
        and not inspect.isabstract(value)
        and not getattr(value, "_is_protocol", False)
        and issubclass(value, FixtureInterface)
    ]
