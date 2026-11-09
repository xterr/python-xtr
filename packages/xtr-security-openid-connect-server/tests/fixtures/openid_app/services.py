"""The services the fixture deployment registers: its session backend.

The session storage is the application's to register — the security bundle
never builds one on its behalf, since a session kept in one process's memory is
lost to every other. The deployment that signs the end-user in with a form keeps
the login there; the others never open a session, so it stays unused for them.
"""

from __future__ import annotations

from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface

__all__ = ["fixture_session_storage"]


@as_service
def fixture_session_storage() -> SessionStorageInterface:
    """The deployment's session storage: in-memory, as a test's own backend."""
    return MemorySessionStorage()
