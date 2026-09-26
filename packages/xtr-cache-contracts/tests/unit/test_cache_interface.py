from __future__ import annotations

from tests.support.in_memory_pool import InMemoryPool
from xtr_cache_contracts import CacheInterface


def test_a_pool_built_on_the_mixin_satisfies_it() -> None:
    assert isinstance(InMemoryPool(), CacheInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), CacheInterface)
