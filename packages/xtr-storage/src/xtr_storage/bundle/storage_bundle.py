"""The xtr-storage bundle: a storage per configured name, and a mount over them all.

An application listing :class:`StorageBundle` gets a
:class:`~xtr_storage.Storage` for every storage in its :class:`StorageConfig`,
qualified by the storage's name and reachable under
:class:`~xtr_storage.StorageOperatorInterface`,
:class:`~xtr_storage.StorageReaderInterface` and
:class:`~xtr_storage.StorageWriterInterface` the same way; the one named
``"default"`` is provided without a qualifier too. A
:class:`~xtr_storage.MountManager` over all of them is provided as well.

Nothing is opened until a storage is first asked for: no directory created, no
bucket reached. Boot checks the configuration without opening anything — every
referenced adapter is registered, every object-store backend is installed, and
no unsupported visibility is asked for — so a mistake fails the application at
startup rather than on its first write. A storage closes what it opened when the
container closes.
"""

from __future__ import annotations

import importlib.util
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, cast, final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    Reference,
    ServiceConfigurator,
    as_bundle,
    named_factory,
)
from xtr_service_contracts import ContainerInterface

from xtr_storage.adapter.in_memory_adapter import InMemoryAdapter
from xtr_storage.adapter.local_adapter import LocalAdapter
from xtr_storage.adapter.path_prefixed_adapter import PathPrefixedAdapter
from xtr_storage.adapter.portable_visibility_converter import PortableVisibilityConverter
from xtr_storage.adapter.read_only_adapter import ReadOnlyAdapter
from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.config import Config
from xtr_storage.exception import InvalidArgumentError
from xtr_storage.mount_manager import MountManager
from xtr_storage.storage import Storage
from xtr_storage.storage_operator_interface import StorageOperatorInterface
from xtr_storage.storage_reader_interface import StorageReaderInterface
from xtr_storage.storage_writer_interface import StorageWriterInterface
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)
from xtr_storage.visibility import Visibility

from .adapter_configs import (
    AdapterEntry,
    FsspecAdapterConfig,
    GcsAdapterConfig,
    LocalAdapterConfig,
    MemoryAdapterConfig,
    S3AdapterConfig,
)
from .storage_config import DEFAULT_STORAGE, StorageConfig
from .storage_definition import StorageDefinition

if TYPE_CHECKING:
    from fsspec import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information
        AbstractFileSystem,
    )

__all__ = ["StorageBundle"]

_STORAGE_INTERFACES: tuple[type, ...] = (
    StorageOperatorInterface,
    StorageReaderInterface,
    StorageWriterInterface,
)


@final
@as_bundle("storage", config=StorageConfig)
class StorageBundle(Bundle[StorageConfig]):
    """Turns a :class:`StorageConfig` into a storage per name, and one mount over them."""

    @override
    def load_extension(
        self,
        config: StorageConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register a storage under each name, its interface aliases, and the mount.

        Each storage is an async-generator factory injecting the configuration
        and the container rather than closing over them, so an ``env(...)``
        placeholder in the configuration is resolved when the storage is built.
        """
        del builder
        for name in config.definitions():
            factory = named_factory(_storage_factory(name), f"storage_{name}")
            _ = services.set(factory, qualifier=name)
            for interface in _STORAGE_INTERFACES:
                services.alias(interface, Storage, alias_qualifier=name, target_qualifier=name)
            if name == DEFAULT_STORAGE:
                services.alias(Storage, Storage, target_qualifier=name)
                for interface in _STORAGE_INTERFACES:
                    services.alias(interface, Storage, target_qualifier=name)

        _ = services.set(_mount_manager)

    @override
    async def boot(self) -> None:
        """Refuse a reference nobody registered, a missing backend, or a bad visibility.

        The configuration is read resolved, so a value given as ``env(...)`` is
        read here, and a variable that is not set fails the boot.

        Raises:
            InvalidArgumentError: Naming the storage whose configuration is wrong.
        """
        container = self.container
        if container is None:  # pragma: no cover — the kernel sets this before boot.
            message = "StorageBundle.boot ran without a container"
            raise RuntimeError(message)

        config = await container.get(StorageConfig)
        for name, definition in config.definitions().items():
            _check_definition(name, definition, container)


def _check_definition(
    name: str,
    definition: StorageDefinition,
    container: ContainerInterface,
) -> None:
    """Refuse anything about one storage that would fail only on first use."""
    entry = definition.adapter
    if isinstance(entry, Reference):
        if not entry.exists_in(container):
            raise InvalidArgumentError(
                f'the "{name}" storage uses {entry}, which the container does not provide.',
            )
    else:
        _check_backend(name, entry)
        _check_visibility(name, definition, entry)

    for generator in (definition.public_url_generator, definition.temporary_url_generator):
        if generator is not None and not generator.exists_in(container):
            raise InvalidArgumentError(
                f'the "{name}" storage uses {generator}, which the container does not provide.',
            )


def _check_backend(name: str, entry: AdapterEntry) -> None:
    """Refuse an object-store adapter whose backend package is not installed."""
    if isinstance(entry, S3AdapterConfig) and importlib.util.find_spec("s3fs") is None:
        raise InvalidArgumentError(
            f'the "{name}" storage needs the "s3fs" package: install "xtr-storage[s3]".',
        )
    if isinstance(entry, GcsAdapterConfig) and importlib.util.find_spec("gcsfs") is None:
        raise InvalidArgumentError(
            f'the "{name}" storage needs the "gcsfs" package: install "xtr-storage[gcs]".',
        )


def _check_visibility(name: str, definition: StorageDefinition, entry: AdapterEntry) -> None:
    """Refuse a visibility named over a backend that has no notion of one."""
    if definition.visibility is None and definition.directory_visibility is None:
        return
    if isinstance(entry, (GcsAdapterConfig, FsspecAdapterConfig)):
        raise InvalidArgumentError(
            f'the "{name}" storage sets a visibility, which its backend does not support.',
        )


async def _mount_manager(config: StorageConfig, container: ContainerInterface) -> MountManager:
    """Build one mount over every configured storage.

    Each storage is resolved from the container, which owns its lifecycle. This
    is a plain factory, not a generator, so the container never runs a cleanup on
    the mount: it must not close the storages it was handed, because it did not
    open them — the container closes each one through its own factory when it
    closes, and closing them here as well would close each one twice.
    """
    storages: dict[str, StorageOperatorInterface] = {
        name: await container.get(Storage, name) for name in config.definitions()
    }

    return MountManager(storages)


def _storage_factory(
    name: str,
) -> Callable[[StorageConfig, ContainerInterface], AsyncIterator[Storage]]:
    """Build the factory of the storage called ``name``.

    One function per storage, so each carries its own name in the container's
    report, and it injects the configuration rather than closing over it.
    """

    async def storage(
        config: StorageConfig,
        container: ContainerInterface,
    ) -> AsyncIterator[Storage]:
        built = await _build_storage(config.definitions()[name], container)
        try:
            yield built
        finally:
            await built.close()

    return storage


async def _build_storage(
    definition: StorageDefinition,
    container: ContainerInterface,
) -> Storage:
    """Build one storage: its adapter, the wrapping it asked for, and its defaults."""
    adapter = await _build_adapter(definition.adapter, container)
    if definition.prefix:
        adapter = PathPrefixedAdapter(adapter, definition.prefix)
    if definition.read_only:
        adapter = ReadOnlyAdapter(adapter)

    public_generator: PublicUrlGeneratorInterface | None = None
    if definition.public_url_generator is not None:
        public_generator = cast(
            "PublicUrlGeneratorInterface",
            await definition.public_url_generator.resolve(container),
        )
    temporary_generator: TemporaryUrlGeneratorInterface | None = None
    if definition.temporary_url_generator is not None:
        temporary_generator = cast(
            "TemporaryUrlGeneratorInterface",
            await definition.temporary_url_generator.resolve(container),
        )

    return Storage(
        adapter,
        _storage_options(definition),
        public_url_generator=public_generator,
        temporary_url_generator=temporary_generator,
    )


def _storage_options(definition: StorageDefinition) -> dict[str, object]:
    """Turn a definition's standing defaults into the options a storage is built with."""
    options: dict[str, object] = {
        Config.RETAIN_VISIBILITY: definition.retain_visibility,
        Config.ALLOW_RELATIVE_PATH_TRAVERSAL: definition.allow_relative_path_traversal,
    }
    if definition.visibility is not None:
        options[Config.VISIBILITY] = Visibility.parse(definition.visibility)
    if definition.directory_visibility is not None:
        options[Config.DIRECTORY_VISIBILITY] = Visibility.parse(definition.directory_visibility)
    if definition.public_url is not None:
        options[Config.PUBLIC_URL] = definition.public_url

    return options


async def _build_adapter(
    entry: AdapterEntry,
    container: ContainerInterface,
) -> StorageAdapterInterface:
    """Build one adapter from its configuration, or fetch the one a reference names.

    The object-store adapters and the generic one are imported here, when a
    storage is first built, so an application without an extra pays nothing until
    it uses that backend.
    """
    if isinstance(entry, Reference):
        return cast("StorageAdapterInterface", await entry.resolve(container))
    if isinstance(entry, LocalAdapterConfig):
        converter = PortableVisibilityConverter(
            file_public=entry.file_public,
            file_private=entry.file_private,
            directory_public=entry.directory_public,
            directory_private=entry.directory_private,
        )
        return LocalAdapter(
            entry.directory,
            visibility=converter,
            link_handling=entry.link_handling,
        )
    if isinstance(entry, MemoryAdapterConfig):
        return InMemoryAdapter(Visibility.parse(entry.default_visibility))
    if isinstance(entry, S3AdapterConfig):
        from xtr_storage.adapter.s3_adapter import S3Adapter  # noqa: PLC0415 -- lazy import

        return S3Adapter(
            entry.bucket,
            entry.prefix,
            region=entry.region,
            endpoint_url=entry.endpoint_url,
            key=entry.key,
            secret=entry.secret,
            token=entry.token,
            anon=entry.anon,
            client_kwargs=entry.client_kwargs,
            config_kwargs=entry.config_kwargs,
            write_options=entry.write_options,
        )
    if isinstance(entry, GcsAdapterConfig):
        from xtr_storage.adapter.gcs_adapter import GcsAdapter  # noqa: PLC0415 -- lazy import

        return GcsAdapter(
            entry.bucket,
            entry.prefix,
            project=entry.project,
            token=entry.token,
            endpoint_url=entry.endpoint_url,
            write_options=entry.write_options,
        )
    # Only an FsspecAdapterConfig remains once the reference and the named
    # configurations above are ruled out.
    import fsspec  # noqa: PLC0415  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information

    from xtr_storage.adapter.generic_fsspec_adapter import GenericFsspecAdapter  # noqa: PLC0415

    filesystem: AbstractFileSystem = fsspec.filesystem(  # pyright: ignore[reportUnknownMemberType,reportAny] -- fsspec ships no type information
        entry.protocol,
        skip_instance_cache=True,
        **entry.options,
    )

    return GenericFsspecAdapter(filesystem, entry.root, closer=_close_built_filesystem)


async def _close_built_filesystem(filesystem: AbstractFileSystem) -> None:
    """Close the session a bundle-built fsspec filesystem opened, if it opened one.

    A storage over a filesystem the application handed in leaves it open — the
    application owns it — but one this bundle built itself is the bundle's to
    shut when the container closes, so the aiohttp session a networked backend
    keeps does not outlive the process.
    """
    session = getattr(filesystem, "_session", None)
    if session is not None:
        await session.close()  # pyright: ignore[reportAny] -- fsspec ships no type information; an async backend keeps its aiohttp session here
