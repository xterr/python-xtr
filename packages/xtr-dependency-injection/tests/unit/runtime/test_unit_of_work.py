"""A unit of work: one scope shared by everything run for one request, message or command."""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import (
    AsyncIterator,  # noqa: TC003 — the engine reads the factory's return annotation
)
from contextlib import AsyncExitStack
from typing import TYPE_CHECKING, TypeVar, final

import anyio
import pytest
import wireup
from typing_extensions import override
from xtr_service_contracts import ContainerInterface

from xtr_dependency_injection import (
    Injected,
    bind_callable,
    current_unit_of_work,
    open_unit_of,
    unit_of_work,
)
from xtr_dependency_injection.exception import InvalidArgumentTypeError, UnitOfWorkClosedError
from xtr_dependency_injection.runtime.wireup_container import WireupContainer

if TYPE_CHECKING:
    from collections.abc import Hashable

T = TypeVar("T")

pytestmark = pytest.mark.anyio


@final
class Session:
    """A scoped service that records whether it was released."""

    def __init__(self) -> None:
        self.closed = False
        self.error: BaseException | None = None


async def session_factory() -> AsyncIterator[Session]:
    session = Session()
    try:
        yield session
    except BaseException as error:
        session.error = error
        raise
    finally:
        session.closed = True


def _container() -> WireupContainer:
    engine = wireup.create_async_container(
        injectables=[wireup.injectable(session_factory, lifetime="scoped")],
    )
    return WireupContainer(engine)


@final
class Counted:
    """A scoped service counting how often it is built."""

    built = 0

    def __init__(self) -> None:
        Counted.built += 1


def _counting_container() -> WireupContainer:
    Counted.built = 0
    engine = wireup.create_async_container(
        injectables=[wireup.injectable(Counted, lifetime="scoped")],
    )
    return WireupContainer(engine)


async def test_a_unit_builds_a_scoped_service_once_and_releases_it_at_the_end() -> None:
    container = _container()

    async with unit_of_work(container) as unit:
        first = await unit.get(Session)
        assert await unit.get(Session) is first
        assert not first.closed

    assert first.closed


async def test_each_unit_has_its_own_scoped_services() -> None:
    container = _container()

    async with unit_of_work(container) as unit:
        first = await unit.get(Session)
    async with unit_of_work(container) as unit:
        second = await unit.get(Session)

    assert first is not second


async def test_a_unit_opened_inside_another_joins_it() -> None:
    container = _container()

    async with unit_of_work(container) as outer:
        session = await outer.get(Session)
        async with unit_of_work(container) as inner:
            assert await inner.get(Session) is session
        assert not session.closed

    assert session.closed


async def test_a_unit_asked_not_to_join_is_one_of_its_own_inside_another() -> None:
    container = _container()

    async with unit_of_work(container) as outer:
        session = await outer.get(Session)
        async with unit_of_work(container, join=False) as inner:
            own = await inner.get(Session)
            assert own is not session
        assert own.closed
        assert await (await _current()).get(Session) is session

    assert session.closed


async def test_a_unit_of_another_container_is_not_joined() -> None:
    first, second = _container(), _container()

    async with unit_of_work(first) as outer:
        own = await outer.get(Session)
        async with unit_of_work(second) as inner:
            other = await inner.get(Session)
            assert other is not own
            assert current_unit_of_work() is not None
        assert other.closed
        assert not own.closed
        assert await (await _current()).get(Session) is own

    assert own.closed


async def test_a_call_bound_on_another_container_does_not_join_the_unit() -> None:
    first, second = _container(), _container()
    received: list[Session] = []

    async def handler(session: Injected[Session]) -> None:
        received.append(session)

    bound = bind_callable(second, handler)
    async with unit_of_work(first) as unit:
        _ = await bound()
        own = await unit.get(Session)

    assert received[0] is not own
    assert received[0].closed


async def _current() -> ContainerInterface:
    unit = current_unit_of_work()
    assert unit is not None
    return unit


async def test_the_error_ending_a_unit_reaches_the_service_s_cleanup() -> None:
    container = _container()
    seen: list[Session] = []

    async def fail_inside_a_unit() -> None:
        async with unit_of_work(container) as unit:
            seen.append(await unit.get(Session))
            raise LookupError

    with pytest.raises(LookupError):
        await fail_inside_a_unit()

    assert seen[0].closed
    assert isinstance(seen[0].error, LookupError)


async def test_bound_callables_share_the_unit_they_are_called_in() -> None:
    container = _container()
    received: list[Session] = []

    async def handler(session: Injected[Session]) -> None:
        received.append(session)

    bound = bind_callable(container, handler)
    async with unit_of_work(container) as unit:
        _ = await bound()
        _ = await bound()
        own = await unit.get(Session)

    assert received[0] is received[1] is own


async def test_bound_callables_outside_a_unit_each_get_their_own() -> None:
    container = _container()
    received: list[Session] = []

    async def handler(session: Injected[Session]) -> None:
        received.append(session)

    bound = bind_callable(container, handler)
    _ = await bound()
    _ = await bound()

    assert received[0] is not received[1]
    assert all(session.closed for session in received)


async def test_a_call_bound_with_its_own_scope_keeps_it_inside_a_unit() -> None:
    container = _container()
    received: list[Session] = []

    async def command(session: Injected[Session]) -> None:
        received.append(session)

    bound = bind_callable(container, command, per_call_scope=True)
    async with unit_of_work(container) as unit:
        _ = await bound()
        own = await unit.get(Session)

    assert received[0] is not own
    assert received[0].closed


async def test_what_a_call_bound_with_its_own_scope_starts_joins_that_scope() -> None:
    container = _container()
    received: list[Session] = []

    async def handler(session: Injected[Session]) -> None:
        received.append(session)

    inner = bind_callable(container, handler)

    async def command(session: Injected[Session]) -> None:
        received.append(session)
        _ = await inner()

    _ = await bind_callable(container, command, per_call_scope=True)()

    assert received[0] is received[1]
    assert received[0].closed


async def test_there_is_no_unit_of_work_outside_one() -> None:
    container = _container()

    assert current_unit_of_work() is None
    async with unit_of_work(container):
        assert current_unit_of_work() is not None
    assert current_unit_of_work() is None


async def test_the_unit_reads_the_container_s_services_and_parameters() -> None:
    engine = wireup.create_async_container(
        injectables=[wireup.injectable(session_factory, lifetime="scoped")],
        config={"app": {"name": "shop"}},
    )
    container = WireupContainer(engine)

    async with unit_of_work(container) as unit:
        assert unit.has(Session)
        assert unit.get_parameter("app.name") == "shop"
        assert unit.has_parameter("app")


async def test_a_unit_that_has_exited_is_gone_from_a_context_copied_inside_it() -> None:
    container = _container()

    async with unit_of_work(container):
        kept = contextvars.copy_context()

    assert kept.run(current_unit_of_work) is None


async def test_a_unit_exited_in_another_task_is_closed_for_every_context() -> None:
    container = _container()
    stack = AsyncExitStack()
    sessions: list[Session] = []
    copies: list[contextvars.Context] = []

    async def open_it() -> None:
        unit = await stack.enter_async_context(unit_of_work(container))
        sessions.append(await unit.get(Session))
        copies.append(contextvars.copy_context())

    await asyncio.create_task(open_it())
    await asyncio.create_task(stack.aclose())

    assert sessions[0].closed
    assert copies[0].run(current_unit_of_work) is None


async def test_a_child_task_outliving_its_unit_cannot_resolve_from_it() -> None:
    container = _counting_container()
    exited = asyncio.Event()

    async def later(unit: ContainerInterface) -> None:
        _ = await exited.wait()
        _ = await unit.get(Counted)

    async with unit_of_work(container) as unit:
        child = asyncio.create_task(later(unit))
    exited.set()

    with pytest.raises(UnitOfWorkClosedError):
        await child
    assert Counted.built == 0


async def test_current_unit_of_work_refuses_once_the_unit_closed() -> None:
    container = _counting_container()

    async with unit_of_work(container):
        kept = await _current()

    with pytest.raises(UnitOfWorkClosedError):
        _ = await kept.get(Counted)
    assert Counted.built == 0


async def test_a_joined_unit_refuses_once_the_unit_it_joined_closed() -> None:
    container = _counting_container()

    async with unit_of_work(container), unit_of_work(container) as joined:
        pass

    with pytest.raises(UnitOfWorkClosedError):
        _ = await joined.get(Counted)
    assert Counted.built == 0


async def test_a_unit_still_open_hands_out_its_shared_instance() -> None:
    container = _counting_container()

    async with unit_of_work(container) as unit:
        first = await unit.get(Counted)
        kept = await _current()

        assert await kept.get(Counted) is first


async def test_open_unit_of_finds_the_unit_open_on_the_containers_services() -> None:
    container = _counting_container()

    async with unit_of_work(container) as unit:
        opened = open_unit_of(container)
        assert opened is not None
        assert await opened.get(Counted) is await unit.get(Counted)

    assert open_unit_of(container) is None


async def test_open_unit_of_finds_no_unit_of_another_container() -> None:
    first, second = _counting_container(), _counting_container()

    async with unit_of_work(first):
        assert open_unit_of(second) is None


async def test_open_unit_of_refuses_a_container_no_kernel_built() -> None:
    with pytest.raises(InvalidArgumentTypeError, match="kernel-provided container"):
        _ = open_unit_of(_Foreign())


async def test_work_that_outlives_the_unit_it_started_in_opens_one_of_its_own() -> None:
    container = _container()
    exited = anyio.Event()
    first: list[Session] = []
    handed: list[tuple[Session, bool]] = []

    async def later() -> None:
        # Started inside the unit, so its context carries it; run once it is over.
        await exited.wait()
        async with unit_of_work(container) as unit:
            session = await unit.get(Session)
            handed.append((session, session.closed))

    async with anyio.create_task_group() as tasks:
        async with unit_of_work(container) as unit:
            first.append(await unit.get(Session))
            _ = tasks.start_soon(later)
        exited.set()

    # Joining the unit that exited would have handed out its released session.
    assert handed[0][0] is not first[0]
    assert handed[0][1] is False


async def test_a_container_no_kernel_built_is_refused() -> None:
    with pytest.raises(InvalidArgumentTypeError, match="kernel-provided container"):
        async with unit_of_work(_Foreign()):
            pass


@final
class _Foreign(ContainerInterface):
    @override
    async def get(self, service: type[T], /, qualifier: Hashable | None = None) -> T:
        raise LookupError(service, qualifier)

    @override
    def has(self, service: type[object], /, qualifier: Hashable | None = None) -> bool:
        del service, qualifier
        return False

    @override
    def get_parameter(self, name: str, /) -> object:
        raise LookupError(name)

    @override
    def has_parameter(self, name: str, /) -> bool:
        del name
        return False
