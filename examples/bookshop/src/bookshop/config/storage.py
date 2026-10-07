"""The storage bundle: the default file store, and a ``reports`` store for exports.

The bundle needs no configuration — unconfigured it gives one ``default`` storage on local
files under ``var/storage``. This module keeps that default and adds a second storage named
``reports``, rooted at the ``catalog`` prefix inside the same directory, so what
``catalog:export`` writes is grouped away from anything else the shop stores. A named storage
is injected qualified — ``Annotated[StorageOperatorInterface, Target("reports")]`` — the way a
named cache pool is.

In tests nothing should touch the disk, so the whole configuration is replaced by memory
storages that start empty and are forgotten when the container closes.
"""

from __future__ import annotations

from xtr_dependency_injection import configure, when
from xtr_storage.bundle import (
    LocalAdapterConfig,
    MemoryAdapterConfig,
    StorageConfig,
    StorageDefinition,
)

__all__ = ["storage", "storage_in_tests"]


@configure
def storage() -> StorageConfig:
    """Local files under the project's ``var/storage``; exports under ``catalog/``."""
    return StorageConfig(
        storages={
            "default": LocalAdapterConfig(),
            "reports": StorageDefinition(adapter=LocalAdapterConfig(), prefix="catalog"),
        },
    )


@configure
@when("test")
def storage_in_tests() -> StorageConfig:
    """Tests write nowhere: both storages live in memory for the run."""
    return StorageConfig(
        storages={"default": MemoryAdapterConfig(), "reports": MemoryAdapterConfig()},
    )
