"""A session storage that keeps its entries in the process's own memory."""

from __future__ import annotations

import pytest

from xtr_http_foundation import MemorySessionStorage

_ID = "0123456789abcdef" * 3


@pytest.mark.anyio
async def test_it_reads_back_what_it_was_written() -> None:
    storage = MemorySessionStorage()

    await storage.write(_ID, {"theme": "dark"}, ttl=None)

    assert await storage.read(_ID) == {"theme": "dark"}


@pytest.mark.anyio
async def test_it_reads_nothing_for_an_id_it_does_not_hold() -> None:
    assert await MemorySessionStorage().read(_ID) is None


@pytest.mark.anyio
async def test_it_copies_the_attributes_in_so_the_caller_lets_go() -> None:
    storage = MemorySessionStorage()
    attributes: dict[str, object] = {"theme": "dark"}

    await storage.write(_ID, attributes, ttl=None)
    attributes["theme"] = "light"

    assert await storage.read(_ID) == {"theme": "dark"}


@pytest.mark.anyio
async def test_it_removes_the_entry() -> None:
    storage = MemorySessionStorage()
    await storage.write(_ID, {"theme": "dark"}, ttl=None)

    await storage.delete(_ID)

    assert await storage.read(_ID) is None


@pytest.mark.anyio
async def test_it_deletes_an_id_it_does_not_hold_without_complaint() -> None:
    storage = MemorySessionStorage()

    await storage.delete(_ID)

    assert await storage.read(_ID) is None
