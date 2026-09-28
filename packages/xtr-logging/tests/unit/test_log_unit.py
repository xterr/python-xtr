from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import anyio
import anyio.lowlevel
import anyio.to_thread
import pytest

from xtr_logging.log_unit import begin_unit, end_unit, unit_state

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _clean_units() -> Iterator[None]:
    """End any unit a synchronous test leaves open in this thread's context."""
    yield
    with contextlib.suppress(BaseException):
        end_unit()


def test_unit_state_is_none_outside_a_unit() -> None:
    assert unit_state(object(), list) is None


def test_begin_unit_opens_a_unit_and_state_is_created() -> None:
    begin_unit()

    state = unit_state(object(), lambda: {"n": 1})

    assert state == {"n": 1}


def test_state_is_created_once_and_returned_on_every_call() -> None:
    begin_unit()
    owner = object()
    calls = 0

    def factory() -> dict[str, int]:
        nonlocal calls
        calls += 1
        return {"n": 0}

    first = unit_state(owner, factory)
    second = unit_state(owner, factory)

    assert first is second
    assert calls == 1


def test_different_owners_get_different_state() -> None:
    begin_unit()
    owner_a = object()
    owner_b = object()

    a = unit_state(owner_a, lambda: [1])
    b = unit_state(owner_b, lambda: [2])

    assert a == [1]
    assert b == [2]


def test_end_unit_runs_callbacks_in_registration_order() -> None:
    begin_unit()
    order: list[str] = []
    owner_a = object()
    owner_b = object()

    _ = unit_state(owner_a, lambda: 1, lambda _s: order.append("a"))
    _ = unit_state(owner_b, lambda: 2, lambda _s: order.append("b"))
    end_unit()

    assert order == ["a", "b"]


def test_a_callback_receives_the_owner_state() -> None:
    begin_unit()
    seen: list[object] = []
    state = unit_state(object(), lambda: {"n": 5}, seen.append)

    end_unit()

    assert seen == [state]


def test_end_unit_runs_every_callback_even_when_one_raises() -> None:
    begin_unit()
    ran: list[str] = []
    owner_boom = object()
    owner_ok = object()

    def boom(_s: object) -> None:
        ran.append("boom")
        raise ValueError("boom")

    def ok(_s: object) -> None:
        ran.append("ok")

    _ = unit_state(owner_boom, lambda: 1, boom)
    _ = unit_state(owner_ok, lambda: 2, ok)

    with pytest.raises(ExceptionGroup) as info:
        end_unit()

    assert ran == ["boom", "ok"]
    assert len(info.value.exceptions) == 1
    assert isinstance(info.value.exceptions[0], ValueError)
    assert unit_state(object(), lambda: 1) is None


def test_end_unit_without_a_unit_is_a_no_op() -> None:
    end_unit()

    assert unit_state(object(), list) is None


def test_begin_unit_ends_an_open_unit_first() -> None:
    begin_unit()
    ended: list[str] = []
    _ = unit_state(object(), lambda: 1, lambda _s: ended.append("first"))

    begin_unit()

    assert ended == ["first"]


@pytest.mark.anyio
async def test_two_concurrent_units_keep_their_own_state() -> None:
    owner = object()
    sizes: list[int] = []
    first_in = anyio.Event()

    def new_list() -> list[int]:
        return []

    async def worker(marker: int, lead: bool) -> None:
        begin_unit()
        state = unit_state(owner, new_list)
        assert state is not None
        state.append(marker)
        if lead:
            first_in.set()
        else:
            await first_in.wait()
        await anyio.lowlevel.checkpoint()
        sizes.append(len(state))
        end_unit()

    async with anyio.create_task_group() as task_group:
        _ = task_group.start_soon(worker, 1, True)  # noqa: FBT003 — anyio.start_soon is positional-only
        _ = task_group.start_soon(worker, 2, False)  # noqa: FBT003 — anyio.start_soon is positional-only

    assert sizes == [1, 1]


@pytest.mark.anyio
async def test_a_sync_function_in_a_thread_mutates_the_same_unit() -> None:
    begin_unit()
    owner = object()
    state = unit_state(owner, lambda: {"n": 0})
    assert state is not None

    def bump() -> None:
        inner = unit_state(owner, lambda: {"n": 99})
        assert inner is not None
        inner["n"] += 1

    await anyio.to_thread.run_sync(bump)

    after = unit_state(owner, lambda: {"n": 0})
    assert after is not None
    assert after["n"] == 1
    end_unit()
