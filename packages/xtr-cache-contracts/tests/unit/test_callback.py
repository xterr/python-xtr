from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from tests.support.in_memory_pool import InMemoryPool

if TYPE_CHECKING:
    from xtr_cache_contracts import Callback, ItemInterface

pytestmark = pytest.mark.anyio


@final
class Loader:
    async def __call__(self, item: ItemInterface) -> str:
        return f"loaded {item.key}"


async def test_an_object_with_an_async_call_is_a_callback() -> None:
    callback: Callback[str] = Loader()

    assert await InMemoryPool().get("k", callback) == "loaded k"


async def test_an_async_function_is_a_callback() -> None:
    async def load(item: ItemInterface) -> int:
        return len(item.key)

    value: int = await InMemoryPool().get("key", load)

    assert value == 3
