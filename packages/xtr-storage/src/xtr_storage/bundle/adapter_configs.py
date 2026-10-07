"""The adapter configurations a storage definition picks between.

Each configuration is the plain data one adapter is built from — a directory, a
bucket, a protocol — and nothing more: no filesystem is opened, no backend is
imported, and no I/O is done until the bundle's factory builds the adapter from
it. They share this module because they are the variants of one tagged union,
the :data:`AdapterEntry` a :class:`~xtr_storage.bundle.StorageDefinition` names.

A configuration validates itself in ``__post_init__`` so a mistake — an empty
bucket, a visibility that names nothing — fails where it is written rather than
on the first attempt to reach a backend. A :class:`Reference` is the sixth
variant: it points the definition at a
:class:`~xtr_storage.adapter.storage_adapter_interface.StorageAdapterInterface`
the container already provides, for an adapter the application builds itself.

A configuration that carries a credential keeps it out of its own ``repr``, and
so does every open-ended option map: an application puts whatever a backend
takes in one — a session token, a passphrase, a signed header — so the map is
treated as a credential whether or not this one holds any. A configuration is
rendered wherever a container is: a diagnostic report, a failed assertion, a
traceback frame, a log line. The value stays readable on the attribute for the
code that needs it, and is simply never printed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TypeAlias

from xtr_dependency_injection import Reference

from xtr_storage.exception import InvalidArgumentError
from xtr_storage.link_handling import LinkHandling
from xtr_storage.visibility import Visibility

__all__ = [
    "AdapterEntry",
    "FsspecAdapterConfig",
    "GcsAdapterConfig",
    "LocalAdapterConfig",
    "MemoryAdapterConfig",
    "S3AdapterConfig",
]


def _empty_options() -> dict[str, object]:
    """Return a fresh option mapping, so two configurations never share one."""
    return {}


@dataclass(frozen=True, slots=True)
class LocalAdapterConfig:
    """Files on the disk of the machine the application runs on.

    The default directory sits under the project's own ``var`` so an
    unconfigured application has somewhere to write without being told one, and
    two projects on one machine never share a tree. The four mode fields are
    what a visibility becomes on disk; a deployment whose web server runs as
    another user widens them.

    Attributes:
        directory: The directory every path is relative to.
        file_public: The mode a file readable by everyone carries.
        file_private: The mode a file readable by its owner alone carries.
        directory_public: The mode a directory everyone may enter carries.
        directory_private: The mode a directory its owner alone may enter carries.
        link_handling: What a listing does with a symbolic link it meets.
    """

    directory: str = "%kernel.project_dir%/var/storage"
    file_public: int = 0o644
    file_private: int = 0o600
    directory_public: int = 0o755
    directory_private: int = 0o700
    link_handling: LinkHandling = LinkHandling.DISALLOW

    def __post_init__(self) -> None:
        """Refuse a directory that is not a non-empty string.

        Raises:
            InvalidArgumentError: When the directory is empty.
        """
        if not isinstance(self.directory, str) or self.directory == "":  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
            raise InvalidArgumentError(
                f"a local storage needs a non-empty directory, got {self.directory!r}",
            )


@dataclass(frozen=True, slots=True)
class MemoryAdapterConfig:
    """Files in a dictionary that vanish with the process.

    What a test reaches for and what an application uses when a storage is only
    somewhere to hand bytes between two steps of one request.

    Attributes:
        default_visibility: What a file is worth when a write named none — a
            :class:`~xtr_storage.Visibility` or the string one carries.
    """

    default_visibility: Visibility | str = Visibility.PUBLIC

    def __post_init__(self) -> None:
        """Refuse a default visibility that names nothing.

        Raises:
            InvalidVisibilityError: When the string names no visibility.
        """
        _ = Visibility.parse(self.default_visibility)


@dataclass(frozen=True, slots=True)
class S3AdapterConfig:
    """A bucket on Amazon S3 or a compatible store, through the ``s3`` extra.

    The credentials are optional because the backend can find them in the
    environment or an instance role; give them here only when the application
    holds them itself. An ``endpoint_url`` points the adapter at a compatible
    store or a local test server.

    Attributes:
        bucket: The bucket every object is stored in.
        prefix: A key prefix under which this storage's objects live.
        region: The bucket's region, used to compose a public url.
        endpoint_url: An alternate endpoint, for a compatible store or emulator.
        key: The access key id, or ``None`` to let the backend find one. Kept
            out of the ``repr``.
        secret: The secret access key, paired with ``key``. Kept out of the
            ``repr``.
        token: A session token, for temporary credentials. Kept out of the
            ``repr``.
        anon: Whether to reach the store without credentials.
        client_kwargs: Extra keyword settings for the underlying client. Kept
            out of the ``repr``.
        config_kwargs: Extra client configuration for the underlying client.
            Kept out of the ``repr``.
        write_options: Default write settings; only known keys are forwarded.
            Kept out of the ``repr``.
    """

    bucket: str
    prefix: str = ""
    region: str | None = None
    endpoint_url: str | None = None
    key: str | None = field(default=None, repr=False)
    secret: str | None = field(default=None, repr=False)
    token: str | None = field(default=None, repr=False)
    anon: bool = False
    client_kwargs: Mapping[str, object] = field(default_factory=_empty_options, repr=False)
    config_kwargs: Mapping[str, object] = field(default_factory=_empty_options, repr=False)
    write_options: Mapping[str, object] = field(default_factory=_empty_options, repr=False)

    def __post_init__(self) -> None:
        """Refuse a bucket that is not a non-empty string.

        Raises:
            InvalidArgumentError: When the bucket is empty.
        """
        if not isinstance(self.bucket, str) or self.bucket == "":  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
            raise InvalidArgumentError(
                f"an s3 storage needs a non-empty bucket, got {self.bucket!r}",
            )


@dataclass(frozen=True, slots=True)
class GcsAdapterConfig:
    """A bucket on Google Cloud Storage, through the ``gcs`` extra.

    Visibility is not offered on this backend in this version, so a definition
    that names one over a bucket configured this way is refused at boot.

    Attributes:
        bucket: The bucket every path lives in.
        prefix: A key prefix within the bucket the caller never sees.
        project: The project the bucket belongs to, for operations that need one.
        token: How the backend authenticates. Kept out of the ``repr``.
        endpoint_url: Where to reach the store, for pointing at an emulator.
        write_options: Settings every write forwards unless a call overrides
            them. Kept out of the ``repr``.
    """

    bucket: str
    prefix: str = ""
    project: str | None = None
    token: str | None = field(default=None, repr=False)
    endpoint_url: str | None = None
    write_options: Mapping[str, object] = field(default_factory=_empty_options, repr=False)

    def __post_init__(self) -> None:
        """Refuse a bucket that is not a non-empty string.

        Raises:
            InvalidArgumentError: When the bucket is empty.
        """
        if not isinstance(self.bucket, str) or self.bucket == "":  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
            raise InvalidArgumentError(
                f"a gcs storage needs a non-empty bucket, got {self.bucket!r}",
            )


@dataclass(frozen=True, slots=True)
class FsspecAdapterConfig:
    """Any other backend, named by its protocol and built for the application.

    A caller who wants a backend this library has no named adapter for — an SFTP
    server, an in-cluster store — names its protocol and the keyword options that
    backend takes, and the bundle builds the filesystem. Visibility is not
    offered, so a definition that names one over such a backend is refused at
    boot.

    Attributes:
        protocol: The filesystem protocol to build, such as ``"memory"``.
        root: What every path is stored under — a directory or a key prefix.
        options: The keyword options the backend is built with — a host, a
            passphrase, a key file. Kept out of the ``repr``.
    """

    protocol: str
    root: str = ""
    options: Mapping[str, object] = field(default_factory=_empty_options, repr=False)

    def __post_init__(self) -> None:
        """Refuse a protocol that is not a non-empty string.

        Raises:
            InvalidArgumentError: When the protocol is empty.
        """
        if not isinstance(self.protocol, str) or self.protocol == "":  # pyright: ignore[reportUnnecessaryIsInstance] -- configs are written by hand; the annotation is not enforced
            raise InvalidArgumentError(
                f"an fsspec storage needs a non-empty protocol, got {self.protocol!r}",
            )


AdapterEntry: TypeAlias = (
    LocalAdapterConfig
    | MemoryAdapterConfig
    | S3AdapterConfig
    | GcsAdapterConfig
    | FsspecAdapterConfig
    | Reference
)
"""One adapter: a configuration the bundle builds, or a service the container provides."""
