"""The services the CSRF fixture registers: its session backend.

The session storage is the application's to register — the bundle never
builds one silently: a session stored in one process's memory is lost to
every other. It registers through a factory naming the interface it answers
as, the way an application reaches for a backend of its own.
"""

from __future__ import annotations

from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface

__all__ = ["fixture_session_storage"]


@as_service
def fixture_session_storage() -> SessionStorageInterface:
    """The fixture's session storage: in-memory, as a test's own backend."""
    return MemorySessionStorage()
