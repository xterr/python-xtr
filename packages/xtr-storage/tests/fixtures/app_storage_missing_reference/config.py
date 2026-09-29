"""A storage pointing a reference at an adapter no service provides; boot must refuse it."""

from __future__ import annotations

from xtr_dependency_injection import Reference, configure

from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.bundle import StorageConfig, StorageDefinition


@configure
def storage() -> StorageConfig:
    return StorageConfig(
        storages={
            "default": StorageDefinition(
                adapter=Reference(StorageAdapterInterface, "absent"),
            ),
        },
    )
