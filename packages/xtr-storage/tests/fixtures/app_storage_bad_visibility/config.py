"""A storage naming a visibility over a backend that has none; boot must refuse it."""

from __future__ import annotations

from xtr_dependency_injection import configure

from xtr_storage.bundle import GcsAdapterConfig, StorageConfig, StorageDefinition


@configure
def storage() -> StorageConfig:
    return StorageConfig(
        storages={
            "gcs": StorageDefinition(
                adapter=GcsAdapterConfig(bucket="uploads"),
                visibility="public",
            ),
        },
    )
