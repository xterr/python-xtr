"""The guard listener a dispatcher keeps runs the one built for the unit of work of each event."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, cast, final

import pytest

from xtr_workflow.bundle._unit_of_work_guard_listener import UnitOfWorkGuardListener
from xtr_workflow.event_listener.guard_listener import GuardListener

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Hashable

    from xtr_dependency_injection import ScopeFactoryInterface

    from xtr_workflow.event import GuardEvent

pytestmark = pytest.mark.anyio


@final
class _RecordingGuardListener:
    def __init__(self) -> None:
        self.heard: list[tuple[object, str]] = []

    async def on_transition(self, event: object, event_name: str) -> None:
        self.heard.append((event, event_name))


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
    def __init__(self, unit: _Unit) -> None:
        self.opened = 0
        self._unit = unit

    @asynccontextmanager
    async def unit_of_work(self, *, join: bool = True) -> AsyncGenerator[_Unit]:
        del join
        self.opened += 1
        yield self._unit


async def test_each_event_runs_the_guard_listener_of_its_unit_of_work() -> None:
    guard_listener = _RecordingGuardListener()
    unit = _Unit(guard_listener)
    scopes = _Scopes(unit)
    listener = UnitOfWorkGuardListener(
        cast("ScopeFactoryInterface", cast("object", scopes)), GuardListener, "article"
    )
    event = cast("GuardEvent", object())

    await listener.on_transition(event, "workflow.article.guard.publish")

    assert scopes.opened == 1
    assert unit.asked == [(GuardListener, "article")]
    assert guard_listener.heard == [(event, "workflow.article.guard.publish")]
