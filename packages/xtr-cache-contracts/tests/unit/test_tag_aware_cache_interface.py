from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.in_memory_pool import InMemoryPool
from xtr_cache_contracts import CacheInterface, TagAwareCacheInterface

if TYPE_CHECKING:
    from collections.abc import Iterable


class TaggedPool(InMemoryPool):
    async def invalidate_tags(self, tags: Iterable[str], /) -> bool:
        return bool(list(tags))


def test_a_cache_that_invalidates_tags_satisfies_it_and_is_still_a_cache() -> None:
    pool = TaggedPool()

    assert isinstance(pool, TagAwareCacheInterface)
    assert isinstance(pool, CacheInterface)


def test_a_cache_without_tags_does_not() -> None:
    assert not isinstance(InMemoryPool(), TagAwareCacheInterface)
