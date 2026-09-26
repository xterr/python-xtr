from __future__ import annotations

from tests.support.in_memory_pool import InMemoryPool
from xtr_cache_contracts import CacheItemPoolInterface


def test_a_pool_satisfies_it() -> None:
    assert isinstance(InMemoryPool(), CacheItemPoolInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), CacheItemPoolInterface)
