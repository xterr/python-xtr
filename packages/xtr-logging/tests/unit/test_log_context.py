from __future__ import annotations

import contextlib
import contextvars
from types import MappingProxyType
from typing import TYPE_CHECKING

import anyio
import pytest

from xtr_logging.log_context import (
    bind_context,
    bound_context,
    clear_context,
    current_context,
    unbind_context,
)
from xtr_logging.log_unit import begin_unit, end_unit

if TYPE_CHECKING:
    from collections.abc import Iterator

    from xtr_logging_contracts import Context


@pytest.fixture(autouse=True)
def _clean_context() -> Iterator[None]:
    clear_context()
    yield
    with contextlib.suppress(BaseException):
        end_unit()
    clear_context()


def test_binding_adds_values() -> None:
    bind_context({"a": 1})
    bind_context({"b": 2})

    assert dict(current_context()) == {"a": 1, "b": 2}


def test_binding_the_same_key_overwrites() -> None:
    bind_context({"a": 1})
    bind_context({"a": 2})

    assert dict(current_context()) == {"a": 2}


def test_binding_copies_the_values_it_is_given() -> None:
    # Given a dict handed to bind_context
    values = {"a": 1}
    bind_context(values)

    # When the caller later mutates that dict
    values["a"] = 2

    # Then the stored context is unmoved — it was copied on the way in
    assert dict(current_context()) == {"a": 1}


def test_the_current_context_is_read_only() -> None:
    bind_context({"a": 1})

    assert isinstance(current_context(), MappingProxyType)


def test_unbinding_removes_keys() -> None:
    bind_context({"a": 1, "b": 2})

    unbind_context("a")

    assert dict(current_context()) == {"b": 2}


def test_unbinding_a_key_that_was_not_bound_is_harmless() -> None:
    bind_context({"a": 1})

    unbind_context("x")

    assert dict(current_context()) == {"a": 1}


def test_clearing_drops_everything() -> None:
    bind_context({"a": 1})

    clear_context()

    assert dict(current_context()) == {}


def test_bound_context_restores_the_previous_state_on_exit() -> None:
    bind_context({"a": 1})

    with bound_context({"b": 2}):
        assert dict(current_context()) == {"a": 1, "b": 2}

    assert dict(current_context()) == {"a": 1}


def test_bound_context_restores_even_when_the_block_raises() -> None:
    bind_context({"a": 1})

    with pytest.raises(RuntimeError), bound_context({"b": 2}):
        raise RuntimeError

    assert dict(current_context()) == {"a": 1}


def test_bound_context_lets_the_inner_binding_win() -> None:
    bind_context({"a": 1})

    with bound_context({"a": 2}):
        assert dict(current_context()) == {"a": 2}

    assert dict(current_context()) == {"a": 1}


def test_what_is_bound_in_a_unit_of_work_is_bound_for_that_unit() -> None:
    begin_unit()
    bind_context({"request_id": "first"})
    assert dict(current_context()) == {"request_id": "first"}

    end_unit()

    assert dict(current_context()) == {}


def test_what_was_bound_outside_any_unit_stays_through_units_and_after_them() -> None:
    bind_context({"worker": "w1"})

    begin_unit()
    bind_context({"request_id": "first"})
    assert dict(current_context()) == {"worker": "w1", "request_id": "first"}
    end_unit()

    assert dict(current_context()) == {"worker": "w1"}


def test_a_unit_begun_where_an_earlier_one_is_still_carried_starts_without_its_keys() -> None:
    bind_context({"worker": "w1"})
    begin_unit()
    bind_context({"request_id": "first", "customer": "ada"})
    # What a server may start the next request from: a copy taken mid-request.
    kept = contextvars.copy_context()
    end_unit()

    def next_request() -> dict[str, object]:
        begin_unit()
        bind_context({"request_id": "second"})
        return dict(current_context())

    assert kept.run(next_request) == {"worker": "w1", "request_id": "second"}


def test_work_that_carries_a_unit_past_its_end_still_reads_what_was_bound_in_it() -> None:
    begin_unit()
    bind_context({"request_id": "first"})
    # A task the request started, still running once the request is over.
    kept = contextvars.copy_context()
    end_unit()

    assert dict(kept.run(current_context)) == {"request_id": "first"}


def test_a_key_unbound_in_a_unit_is_back_once_the_unit_is_over() -> None:
    bind_context({"worker": "w1"})
    begin_unit()

    unbind_context("worker")
    assert dict(current_context()) == {}
    end_unit()

    assert dict(current_context()) == {"worker": "w1"}


def test_bound_context_in_a_unit_restores_what_the_unit_had_bound() -> None:
    begin_unit()
    bind_context({"request_id": "first"})

    with bound_context({"step": "charge"}):
        assert dict(current_context()) == {"request_id": "first", "step": "charge"}

    assert dict(current_context()) == {"request_id": "first"}


@pytest.mark.anyio
async def test_two_tasks_keep_separate_bindings() -> None:
    # Given two workers that each bind their own key, then read once both have
    a_bound = anyio.Event()
    b_bound = anyio.Event()
    seen: dict[str, Context] = {}

    async def worker(name: str, mine: anyio.Event, theirs: anyio.Event) -> None:
        bind_context({name: name})
        mine.set()
        await theirs.wait()
        seen[name] = current_context()

    # When they run concurrently
    async with anyio.create_task_group() as tg:
        _ = tg.start_soon(worker, "a", a_bound, b_bound)
        _ = tg.start_soon(worker, "b", b_bound, a_bound)

    # Then neither sees the other's binding, though both had bound before reading
    assert seen["a"]["a"] == "a"
    assert "b" not in seen["a"]
    assert seen["b"]["b"] == "b"
    assert "a" not in seen["b"]
