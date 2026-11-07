"""The services the client application registers: its session backend.

The login keeps its ``state``, ``nonce`` and proof key in the session between
the redirect to the provider and the way back, so the application registers
where sessions live — in memory, as a test's own backend.
"""

from __future__ import annotations

from xtr_dependency_injection import as_service
from xtr_http_foundation import MemorySessionStorage, SessionStorageInterface

__all__ = ["client_session_storage"]


@as_service
def client_session_storage() -> SessionStorageInterface:
    """The client application's session storage: in-memory."""
    return MemorySessionStorage()
