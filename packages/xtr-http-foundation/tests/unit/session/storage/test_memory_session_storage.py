"""A session storage that keeps its entries in the process's own memory."""

from __future__ import annotations

from typing import cast

import pytest

from xtr_http_foundation import MemorySessionStorage
from xtr_http_foundation.exception import InvalidArgumentError

_ID = "0123456789abcdef" * 3


@pytest.mark.anyio
async def test_it_reads_back_what_it_was_written() -> None:
    storage = MemorySessionStorage()

    _ = await storage.write(_ID, {"theme": "dark"}, ttl=None)

    assert await storage.read(_ID) == {"theme": "dark"}


@pytest.mark.anyio
async def test_it_reads_nothing_for_an_id_it_does_not_hold() -> None:
    assert await MemorySessionStorage().read(_ID) is None


@pytest.mark.anyio
async def test_it_copies_the_attributes_in_so_the_caller_lets_go() -> None:
    storage = MemorySessionStorage()
    attributes: dict[str, object] = {"theme": "dark"}

    _ = await storage.write(_ID, attributes, ttl=None)
    attributes["theme"] = "light"

    assert await storage.read(_ID) == {"theme": "dark"}


@pytest.mark.anyio
async def test_it_removes_the_entry() -> None:
    storage = MemorySessionStorage()
    _ = await storage.write(_ID, {"theme": "dark"}, ttl=None)

    await storage.delete(_ID)

    assert await storage.read(_ID) is None


@pytest.mark.anyio
async def test_it_deletes_an_id_it_does_not_hold_without_complaint() -> None:
    storage = MemorySessionStorage()

    await storage.delete(_ID)

    assert await storage.read(_ID) is None


@pytest.mark.anyio
async def test_mutating_what_was_read_does_not_reach_the_store() -> None:
    storage = MemorySessionStorage()
    _ = await storage.write(_ID, {"cart": ["book"]}, ttl=None)
    read = await storage.read(_ID)
    assert read is not None
    cart = read["cart"]
    assert isinstance(cart, list)

    cast("list[object]", cart).append("pen")

    assert await storage.read(_ID) == {"cart": ["book"]}


@pytest.mark.anyio
async def test_it_refuses_to_write_an_entry_that_must_exist_but_is_gone() -> None:
    storage = MemorySessionStorage()

    written = await storage.write(_ID, {"theme": "dark"}, ttl=None, must_exist=True)

    assert written is False
    assert await storage.read(_ID) is None


@pytest.mark.anyio
async def test_it_refuses_a_value_that_does_not_round_trip_through_json() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = await MemorySessionStorage().write(_ID, {"tags": {"a"}}, ttl=None)
