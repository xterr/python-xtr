"""The guard listener a dispatcher keeps runs the one built for the unit of work of each event."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast, final

import pytest

from xtr_workflow import Transition
from xtr_workflow.bundle._unit_of_work_guard_listener import UnitOfWorkGuardListener
from xtr_workflow.event_listener.guard_listener import GuardListener

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Hashable

    from xtr_dependency_injection import ScopeFactoryInterface

    from xtr_workflow.event import GuardEvent

pytestmark = pytest.mark.anyio


@final
class _RecordingGuardListener:
    def __init__(self, journal: list[str]) -> None:
        self.heard: list[tuple[object, str]] = []
        self._journal = journal

    async def on_transition(self, event: object, event_name: str) -> None:
        self.heard.append((event, event_name))

    def get_guard_names(self, event_name: str, transition: Transition) -> list[str]:
        self._journal.append("guards named")
        return [f"{event_name}: {transition.get_name()}"]


@final
class _Unit:
    def __init__(self, listener: _RecordingGuardListener) -> None:
        self.asked: list[tuple[type, Hashable | None]] = []
        self._listener = listener

    async def get(self, service: type, qualifier: Hashable | None = None) -> object:
        self.asked.append((service, qualifier))
        return self._listener


@final
class _Scopes:
    """Opens the one unit of work it has, noting in the journal when it opens and closes."""

    def __init__(self, unit: _Unit, journal: list[str]) -> None:
        self.opened = 0
        self._unit = unit
        self._journal = journal

    @asynccontextmanager
    async def unit_of_work(self, *, join: bool = True) -> AsyncGenerator[_Unit]:
        del join
        self.opened += 1
        self._journal.append("unit opened")
        try:
            yield self._unit
        finally:
            self._journal.append("unit closed")


async def test_each_event_runs_the_guard_listener_of_its_unit_of_work() -> None:
    journal: list[str] = []
    guard_listener = _RecordingGuardListener(journal)
    unit = _Unit(guard_listener)
    scopes = _Scopes(unit, journal)
    listener = UnitOfWorkGuardListener(
        cast("ScopeFactoryInterface", cast("object", scopes)), GuardListener, "article"
    )
    event = cast("GuardEvent", object())

    await listener.on_transition(event, "workflow.article.guard.publish")

    assert scopes.opened == 1
    assert unit.asked == [(GuardListener, "article")]
    assert guard_listener.heard == [(event, "workflow.article.guard.publish")]


async def test_it_names_the_guards_inside_the_unit_of_work_it_opens() -> None:
    journal: list[str] = []
    unit = _Unit(_RecordingGuardListener(journal))
    scopes = _Scopes(unit, journal)
    listener = UnitOfWorkGuardListener(
        cast("ScopeFactoryInterface", cast("object", scopes)), GuardListener, "article"
    )
    publish = Transition("publish", "draft", "published")

    names = await listener.get_guard_names("workflow.article.guard.publish", publish)

    assert names == ["workflow.article.guard.publish: publish"]
    assert unit.asked == [(GuardListener, "article")]
    assert journal == ["unit opened", "guards named", "unit closed"]
