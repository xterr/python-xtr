"""The services the stateful fixture registers: its session and cache backends.

The session storage and the cache pool are the application's to register —
the bundle never builds either silently: a session stored in one process's
memory or an ended session remembered on one server are lost to every other.
Both register through a factory naming the interface they answer as, the way
an application reaches for a backend of its own.
"""

from __future__ import annotations

from xtr_cache import ArrayAdapter, CacheItemPoolInterface
from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface

__all__ = ["fixture_cache_pool", "fixture_session_storage"]


@as_service
def fixture_session_storage() -> SessionStorageInterface:
    """The fixture's session storage: in-memory, as a test's own backend."""
    return MemorySessionStorage()


@as_service
def fixture_cache_pool() -> CacheItemPoolInterface:
    """The fixture's cache pool: in-memory, as a test's own backend."""
    return ArrayAdapter()
