"""The xtr-dependency-injection bundle for xtr-storage."""

from __future__ import annotations

from .adapter_configs import (
    AdapterEntry,
    FsspecAdapterConfig,
    GcsAdapterConfig,
    LocalAdapterConfig,
    MemoryAdapterConfig,
    S3AdapterConfig,
)
from .storage_bundle import StorageBundle
from .storage_config import DEFAULT_STORAGE, StorageConfig
from .storage_definition import StorageDefinition

__all__ = [
    "DEFAULT_STORAGE",
    "AdapterEntry",
    "FsspecAdapterConfig",
    "GcsAdapterConfig",
    "LocalAdapterConfig",
    "MemoryAdapterConfig",
    "S3AdapterConfig",
    "StorageBundle",
    "StorageConfig",
    "StorageDefinition",
]
