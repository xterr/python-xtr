"""A storage built on an adapter the container provides, named by a reference."""

from __future__ import annotations

from xtr_dependency_injection import Reference, configure

from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.bundle import StorageConfig, StorageDefinition

from .services import ADAPTER


@configure
def storage() -> StorageConfig:
    return StorageConfig(
        storages={
            "default": StorageDefinition(adapter=Reference(StorageAdapterInterface, ADAPTER)),
        },
    )
