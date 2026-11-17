from __future__ import annotations

import anyio
import anyio.lowlevel
import pytest
from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging import DebugHandler, begin_unit, end_unit


def test_outside_a_unit_nothing_is_kept() -> None:
    handler = DebugHandler()

    assert handler.handle(make_record()) is False
    assert handler.get_logs() == ()


def test_the_records_of_the_open_unit_are_kept_in_order() -> None:
    handler = DebugHandler()
    first, second = make_record(message="one"), make_record(Level.ERROR, "two")

    begin_unit()
    try:
        _ = handler.handle(first)
        _ = handler.handle(second)

        assert handler.get_logs() == (first, second)
        assert handler.count_errors() == 1
    finally:
        end_unit()


def test_the_records_are_let_go_of_when_the_unit_ends() -> None:
    handler = DebugHandler()
    begin_unit()
    _ = handler.handle(make_record())
    end_unit()

    begin_unit()
    try:
        assert handler.get_logs() == ()
    finally:
        end_unit()


def test_records_below_the_level_are_not_kept() -> None:
    handler = DebugHandler(Level.WARNING)

    begin_unit()
    try:
        _ = handler.handle(make_record(Level.INFO))

        assert handler.get_logs() == ()
    finally:
        end_unit()


@pytest.mark.anyio
async def test_concurrent_units_keep_their_own_records() -> None:
    handler = DebugHandler()
    seen: dict[str, tuple[str, ...]] = {}

    async def unit(name: str) -> None:
        begin_unit()
        try:
            _ = handler.handle(make_record(message=name))
            await anyio.lowlevel.checkpoint()
            seen[name] = tuple(record.message for record in handler.get_logs())
        finally:
            end_unit()

    async with anyio.create_task_group() as group:
        _ = group.start_soon(unit, "first")
        _ = group.start_soon(unit, "second")

    assert seen == {"first": ("first",), "second": ("second",)}
