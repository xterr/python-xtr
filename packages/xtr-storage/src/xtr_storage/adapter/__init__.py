"""Where the bytes actually live: one adapter per kind of backend."""

from __future__ import annotations

from .fsspec_adapter import FsspecAdapter
from .gcs_adapter import GcsAdapter
from .generic_fsspec_adapter import GenericFsspecAdapter
from .in_memory_adapter import InMemoryAdapter
from .local_adapter import LocalAdapter
from .path_prefixed_adapter import PathPrefixedAdapter
from .portable_visibility_converter import PortableVisibilityConverter
from .read_only_adapter import ReadOnlyAdapter
from .s3_adapter import S3Adapter
from .storage_adapter_interface import StorageAdapterInterface
from .visibility_converter_interface import VisibilityConverterInterface

__all__ = [
    "FsspecAdapter",
    "GcsAdapter",
    "GenericFsspecAdapter",
    "InMemoryAdapter",
    "LocalAdapter",
    "PathPrefixedAdapter",
    "PortableVisibilityConverter",
    "ReadOnlyAdapter",
    "S3Adapter",
    "StorageAdapterInterface",
    "VisibilityConverterInterface",
]
