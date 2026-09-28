from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import anyio
import anyio.lowlevel
import anyio.to_thread
import pytest

from tests.support.records import make_record
from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.log_unit import begin_unit, end_unit, unit_state
from xtr_logging.processor.uid_processor import UidProcessor

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(autouse=True)
def _clean_units() -> Iterator[None]:
    """End any unit a synchronous test leaves open in this thread's context."""
    yield
    with contextlib.suppress(BaseException):
        end_unit()


def test_it_adds_a_uid_of_the_requested_length() -> None:
    processor = UidProcessor(10)

    record = processor(make_record())

    assert record.extra["uid"] == processor.uid
    assert len(processor.uid) == 10


def test_the_default_length_is_seven() -> None:
    assert len(UidProcessor().uid) == 7


def test_the_same_uid_rides_every_record_until_reset() -> None:
    processor = UidProcessor()

    first = processor(make_record())
    second = processor(make_record())

    assert first.extra["uid"] == second.extra["uid"]


def test_reset_mints_a_new_uid() -> None:
    processor = UidProcessor()
    before = processor.uid

    processor.reset()

    assert processor.uid != before


def test_a_length_below_one_is_refused() -> None:
    with pytest.raises(InvalidOptionError):
        _ = UidProcessor(0)


def test_a_length_above_thirty_two_is_refused() -> None:
    with pytest.raises(InvalidOptionError):
        _ = UidProcessor(33)


def test_inside_a_unit_the_uid_comes_from_the_unit_not_the_instance() -> None:
    processor = UidProcessor()
    instance_uid = processor.uid
    begin_unit()

    unit_uid = processor.uid

    assert unit_uid != instance_uid
    assert processor(make_record()).extra["uid"] == unit_uid
    end_unit()


def test_the_instance_uid_returns_outside_the_unit() -> None:
    processor = UidProcessor()
    instance_uid = processor.uid
    begin_unit()
    _ = processor.uid
    end_unit()

    assert processor.uid == instance_uid


def test_reset_inside_a_unit_mints_a_new_uid_for_that_unit_only() -> None:
    processor = UidProcessor()
    instance_uid = processor.uid
    begin_unit()
    before = processor.uid

    processor.reset()

    assert processor.uid != before
    end_unit()
    assert processor.uid == instance_uid


@pytest.mark.anyio
async def test_two_concurrent_units_get_distinct_stable_uids() -> None:
    processor = UidProcessor()
    seen: dict[int, set[str]] = {1: set(), 2: set()}
    first_in = anyio.Event()

    async def worker(marker: int, lead: bool) -> None:
        begin_unit()
        seen[marker].add(processor.uid)
        if lead:
            first_in.set()
        else:
            await first_in.wait()
        await anyio.lowlevel.checkpoint()
        seen[marker].add(processor.uid)
        end_unit()

    async with anyio.create_task_group() as task_group:
        _ = task_group.start_soon(worker, 1, True)  # noqa: FBT003 — anyio.start_soon is positional-only
        _ = task_group.start_soon(worker, 2, False)  # noqa: FBT003 — anyio.start_soon is positional-only

    assert len(seen[1]) == 1
    assert len(seen[2]) == 1
    assert seen[1] != seen[2]


@pytest.mark.anyio
async def test_a_sync_call_in_a_thread_shares_the_unit_uid() -> None:
    processor = UidProcessor()
    begin_unit()
    unit_uid = processor.uid

    def read_and_reset() -> str:
        seen = processor.uid
        processor.reset()
        return seen

    seen_in_thread = await anyio.to_thread.run_sync(read_and_reset)

    assert seen_in_thread == unit_uid
    assert processor.uid != unit_uid
    end_unit()


def test_unit_state_holds_the_uid_box_for_the_processor() -> None:
    processor = UidProcessor()
    begin_unit()

    _ = processor.uid
    box = unit_state(processor, lambda: None)

    assert box is not None
    end_unit()
