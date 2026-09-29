"""The application's own storage adapter, which the storage points a reference at."""

from __future__ import annotations

from xtr_dependency_injection import as_service

from xtr_storage.adapter.in_memory_adapter import InMemoryAdapter
from xtr_storage.adapter.storage_adapter_interface import (  # noqa: TC001 -- the container reads the return annotation at runtime
    StorageAdapterInterface,
)

ADAPTER = "app_adapter"


@as_service(qualifier=ADAPTER)
def adapter() -> StorageAdapterInterface:
    return InMemoryAdapter()
