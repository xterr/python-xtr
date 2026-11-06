"""The services the parameter paths fixture registers: its session backend."""

from __future__ import annotations

from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface

__all__ = ["fixture_session_storage"]


@as_service
def fixture_session_storage() -> SessionStorageInterface:
    """The fixture's session storage: in-memory, as a test's own backend."""
    return MemorySessionStorage()
