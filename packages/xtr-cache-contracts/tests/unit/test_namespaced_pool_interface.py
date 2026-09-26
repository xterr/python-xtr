from __future__ import annotations

from typing import Self, final

from tests.support.in_memory_pool import InMemoryPool
from xtr_cache_contracts import NamespacedPoolInterface


@final
class NamespacedPool:
    def __init__(self, namespace: str = "") -> None:
        self.namespace = namespace

    def with_sub_namespace(self, namespace: str, /) -> Self:
        return type(self)(f"{self.namespace}{namespace}:")


def test_a_pool_with_sub_namespaces_satisfies_it() -> None:
    pool = NamespacedPool()

    assert isinstance(pool, NamespacedPoolInterface)
    assert pool.with_sub_namespace("tenant42").namespace == "tenant42:"
    assert pool.namespace == ""


def test_a_pool_without_them_does_not() -> None:
    assert not isinstance(InMemoryPool(), NamespacedPoolInterface)
