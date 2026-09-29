"""Configuration for :class:`~xtr_storage.bundle.storage_bundle.StorageBundle`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from xtr_dependency_injection import Reference

from xtr_storage.exception import InvalidArgumentError

from .adapter_configs import (
    AdapterEntry,
    FsspecAdapterConfig,
    GcsAdapterConfig,
    LocalAdapterConfig,
    MemoryAdapterConfig,
    S3AdapterConfig,
)
from .storage_definition import StorageDefinition

__all__ = ["DEFAULT_STORAGE", "StorageConfig"]

DEFAULT_STORAGE = "default"
"""The storage whose services are provided without a qualifier too."""

_ADAPTER_CONFIG_TYPES: tuple[type, ...] = (
    LocalAdapterConfig,
    MemoryAdapterConfig,
    S3AdapterConfig,
    GcsAdapterConfig,
    FsspecAdapterConfig,
    Reference,
)


def _default_storages() -> dict[str, StorageDefinition]:
    return {DEFAULT_STORAGE: StorageDefinition()}


@dataclass(frozen=True, slots=True)
class StorageConfig:
    """Which storages exist, and how each one is built.

    Every storage becomes a :class:`~xtr_storage.Storage` qualified by its name,
    reachable under the reader, writer and operator interfaces the same way; the
    one named ``"default"`` is provided without a qualifier too. A
    :class:`~xtr_storage.MountManager` over all of them is provided as well.

    An entry is either a full :class:`StorageDefinition` or, as a shorthand, a
    bare adapter configuration — a
    :class:`~xtr_storage.bundle.LocalAdapterConfig` and the like, or a
    :class:`Reference` to an adapter the container provides — which is read as a
    definition with that adapter and everything else left at its default.

    ```python
    StorageConfig(
        storages={
            "default": LocalAdapterConfig(),
            "avatars": StorageDefinition(adapter=S3AdapterConfig("uploads"), prefix="avatars"),
        }
    )
    ```

    Attributes:
        storages: Each storage by name. An empty mapping means the default.
    """

    storages: Mapping[str, StorageDefinition | AdapterEntry] = field(
        default_factory=_default_storages,
    )

    def __post_init__(self) -> None:
        """Refuse a storage that is not named, or an entry that is neither kind.

        Raises:
            InvalidArgumentError: When the configuration cannot be read.
        """
        for name, entry in self.storages.items():
            if not isinstance(name, str) or not name:  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
                raise InvalidArgumentError(
                    f"a storage needs a non-empty name, got {name!r}",
                )
            if not isinstance(entry, (StorageDefinition, *_ADAPTER_CONFIG_TYPES)):
                raise InvalidArgumentError(
                    f'the "{name}" storage must be a StorageDefinition or an adapter '
                    f"configuration, got {entry!r}",
                )

    def definitions(self) -> dict[str, StorageDefinition]:
        """Return every storage as a full definition; the default when none is set.

        A bare adapter configuration is wrapped in a
        :class:`StorageDefinition` naming it, so callers see one shape.
        """
        storages = self.storages or _default_storages()

        return {
            name: entry
            if isinstance(entry, StorageDefinition)
            else StorageDefinition(adapter=entry)
            for name, entry in storages.items()
        }
