"""The in-memory fake keeps the pool contract it stands in for."""

from __future__ import annotations

from datetime import timedelta

import pytest
from xtr_clock.testing import mock_time

from tests.support.in_memory_pool import InMemoryPool
from xtr_cache_contracts import CacheItemPoolInterface, InvalidArgumentError

pytestmark = pytest.mark.anyio


def test_it_is_a_pool() -> None:
    assert isinstance(InMemoryPool(), CacheItemPoolInterface)


async def test_a_key_never_saved_is_a_miss() -> None:
    item = await InMemoryPool().get_item("absent")

    assert item.key == "absent"
    assert not item.is_hit()
    assert item.get() is None


async def test_a_saved_none_is_a_hit() -> None:
    pool = InMemoryPool()

    assert await pool.save((await pool.get_item("k")).set(None))

    assert (await pool.get_item("k")).is_hit()


async def test_an_item_expires_after_its_lifetime() -> None:
    pool = InMemoryPool()
    with mock_time("2024-04-09 12:00:00") as clock:
        _ = await pool.save((await pool.get_item("k")).set(1).expires_after(timedelta(seconds=10)))

        clock.sleep(9)
        assert await pool.has_item("k")
        clock.sleep(1)
        assert not await pool.has_item("k")


async def test_a_lifetime_of_zero_removes_the_key() -> None:
    pool = InMemoryPool()
    _ = await pool.save((await pool.get_item("k")).set(1))

    assert await pool.save((await pool.get_item("k")).set(2).expires_after(0))

    assert not await pool.has_item("k")


async def test_a_deferred_item_is_stored_on_commit() -> None:
    pool = InMemoryPool()

    assert await pool.save_deferred((await pool.get_item("k")).set(1))
    assert await pool.commit()

    assert (await pool.get_item("k")).get() == 1


async def test_reading_a_deferred_key_commits_it_first() -> None:
    pool = InMemoryPool()
    _ = await pool.save_deferred((await pool.get_item("k")).set(1))

    assert (await pool.get_item("k")).get() == 1


async def test_items_come_back_for_every_key_in_the_order_asked() -> None:
    pool = InMemoryPool()
    _ = await pool.save((await pool.get_item("b")).set(2))

    items = await pool.get_items(["c", "b", "a"])

    assert list(items) == ["c", "b", "a"]
    assert [item.is_hit() for item in items.values()] == [False, True, False]


async def test_deleting_removes_the_items_and_a_missing_key_is_fine() -> None:
    pool = InMemoryPool()
    _ = await pool.save((await pool.get_item("a")).set(1))

    assert await pool.delete_items(["a", "never"])

    assert not await pool.has_item("a")


async def test_clearing_a_prefix_keeps_the_other_keys() -> None:
    pool = InMemoryPool()
    _ = await pool.save((await pool.get_item("user.1")).set(1))
    _ = await pool.save((await pool.get_item("order.1")).set(1))

    assert await pool.clear("user.")

    assert not await pool.has_item("user.1")
    assert await pool.has_item("order.1")


async def test_an_item_from_another_pool_is_not_saved() -> None:
    pool = InMemoryPool()
    foreign = await InMemoryPool().get_item("k")

    assert not await pool.save(foreign)
    assert not await pool.save_deferred(foreign)


async def test_a_failing_backend_reports_false() -> None:
    pool = InMemoryPool()
    pool.fail_saves = True

    assert not await pool.save((await pool.get_item("k")).set(1))


async def test_tags_are_stored_in_the_metadata() -> None:
    pool = InMemoryPool()

    _ = await pool.save((await pool.get_item("k")).set(1).tag("a").tag(["b", "a"]))

    assert (await pool.get_item("k")).metadata == {"tags": ("a", "b")}


@pytest.mark.parametrize("key", ["", "a:b", "a/b", "{a}"])
async def test_an_invalid_key_is_refused(key: str) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = await InMemoryPool().get_item(key)
