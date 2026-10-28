"""The services the fixture registers: its session backend and its counters.

The session storage is the application's to register — the bundle never
builds one silently. So is the storage the login throttling counts in: an
application that throttles its logins hands the counters a place to live,
which here is this process's memory, as a test's own backend.
"""

from __future__ import annotations

from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface
from xtr_rate_limiter import InMemoryStorage
from xtr_rate_limiter.storage.storage_interface import StorageInterface

__all__ = ["fixture_login_counters", "fixture_session_storage"]


@as_service
def fixture_session_storage() -> SessionStorageInterface:
    """The fixture's session storage: in-memory, as a test's own backend."""
    return MemorySessionStorage()


@as_service
def fixture_login_counters() -> StorageInterface:
    """The fixture's login counters: in-memory, as a test's own backend."""
    return InMemoryStorage()
