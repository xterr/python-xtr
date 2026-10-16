"""The storages a session can persist through.

The cache-pool storage is not re-exported here: it needs the ``cache``
extra, and reaching for it by name —
``xtr_http_foundation.session.storage.cache_pool_session_storage`` — is what
turns the extra on.
"""

from __future__ import annotations

from .memory_session_storage import MemorySessionStorage
from .session_storage_interface import SessionStorageInterface

__all__ = [
    "MemorySessionStorage",
    "SessionStorageInterface",
]
