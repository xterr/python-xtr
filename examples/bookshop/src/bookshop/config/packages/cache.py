"""The cache: the app pool in files, a pool for quotes; memory in tests.

The ``app`` pool is provided without a qualifier; every other pool under its name. The
scheduler bundle adds a ``scheduler`` pool here too, on the app pool's adapter — see
``bookshop.scheduling.shop_schedule`` for what uses it. ``bookshop cache:pool:list`` names
them all.
"""

from __future__ import annotations

from xtr_cache.bundle import CacheConfig, PoolConfig
from xtr_dependency_injection import configure, when

__all__ = ["cache", "cache_in_tests"]


@configure
def cache() -> CacheConfig:
    """Files under the kernel's share directory, so saved state outlives a command run."""
    return CacheConfig(pools={"quotes": PoolConfig(default_lifetime=300)})


@configure
@when("test")
def cache_in_tests() -> CacheConfig:
    """Tests start from nothing: every pool in memory, no stampede locks on disk."""
    return CacheConfig(app="array", pools={"quotes": "array"}, stampede_lock=None)
