"""The services the form-login fixture registers: its session backend.

The session storage is the application's to register — the bundle never
builds one silently. Here it is a cache pool in this process's memory: the
storage that keeps a session as JSON and nothing else, which is what a shared
backend keeps it as too.
"""

from __future__ import annotations

from xtr_cache import ArrayAdapter
from xtr_dependency_injection import as_service
from xtr_http_foundation import SessionStorageInterface
from xtr_http_foundation.session.storage.cache_pool_session_storage import (
    CachePoolSessionStorage,
)

__all__ = ["fixture_session_storage"]


@as_service
def fixture_session_storage() -> SessionStorageInterface:
    """The fixture's session storage: a cache pool, keeping every session as JSON."""
    return CachePoolSessionStorage(ArrayAdapter())
