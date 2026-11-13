"""A bound call's own scope, however the call is driven."""

from __future__ import annotations

import contextvars
import inspect
import types
from collections.abc import (
    AsyncIterator,  # noqa: TC003 — the engine reads the factory's return annotation
)
from typing import TYPE_CHECKING, final

import pytest
import wireup

from xtr_dependency_injection import Injected, bind_callable
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
