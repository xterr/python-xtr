"""A bound call's own scope, however the call is driven."""

from __future__ import annotations

import asyncio
import contextvars
import inspect
import types
from collections.abc import (
    AsyncIterator,  # noqa: TC003 — the engine reads the factory's return annotation
)
from typing import TYPE_CHECKING, final

import pytest
import wireup

from xtr_dependency_injection import Injected, bind_callable, unit_of_work
from xtr_dependency_injection.exception import UnitOfWorkClosedError
from xtr_dependency_injection.runtime.wireup_container import WireupContainer

if TYPE_CHECKING:
    from collections.abc import Generator

pytestmark = pytest.mark.anyio


@final
class Session:
    """A scoped service that records whether it was released."""

    def __init__(self) -> None:
        self.closed = False


async def session_factory() -> AsyncIterator[Session]:
    session = Session()
    try:
        yield session
    finally:
        session.closed = True


def _container() -> WireupContainer:
    engine = wireup.create_async_container(
        injectables=[wireup.injectable(session_factory, lifetime="scoped")],
    )
    return WireupContainer(engine)


@types.coroutine
def _suspend() -> Generator[None]:
    """Hand control back to whoever steps the coroutine, as an awaited I/O would."""
    yield


@final
class Slow:
    """A scoped service whose factory takes its time."""


@final
class Handler:
    """A scoped handler class, counting how often it is built."""

    built = 0

    def __init__(self) -> None:
        Handler.built += 1

    async def __call__(self, slow: Injected[Slow]) -> None:
        del slow


async def test_a_per_call_scope_exited_in_another_context_does_not_raise() -> None:
    received: list[Session] = []

    async def command(session: Injected[Session]) -> None:
        received.append(session)
        await _suspend()

    call = bind_callable(_container(), command, per_call_scope=True)()
    assert inspect.iscoroutine(call)
    # Started in one context and finished in another, as a coroutine handed
    # between tasks is.
    contextvars.copy_context().run(call.send, None)
    with pytest.raises(StopIteration):
        contextvars.copy_context().run(call.send, None)

    assert received[0].closed


async def test_a_joined_call_whose_unit_closed_meanwhile_raises() -> None:
    building = asyncio.Event()
    release = asyncio.Event()

    async def slow_factory() -> Slow:
        building.set()
        _ = await release.wait()
        return Slow()

    Handler.built = 0
    container = WireupContainer(
        wireup.create_async_container(
            injectables=[
                wireup.injectable(slow_factory, lifetime="scoped"),
                wireup.injectable(Handler, lifetime="scoped"),
            ],
        )
    )
    bound = bind_callable(container, Handler)

    async def call_it() -> None:
        _ = await bound()

    async with unit_of_work(container):
        call = asyncio.create_task(call_it())
        _ = await building.wait()
    release.set()

    with pytest.raises(UnitOfWorkClosedError):
        await call
    assert Handler.built == 0
