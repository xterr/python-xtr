"""A storage backed by Google Cloud Storage, spoken to through ``gcsfs``.

An object store keeps keys, not directories, so this adds to the shared base
what a real filesystem would have given for free: a zero-byte object standing in
for an empty directory, a listing that hides that marker, and an existence check
that answers for a directory the store never recorded — all borrowed from
:mod:`~xtr_storage.adapter._object_store`, so this adapter and the S3 one answer
directory questions the same way.

Three capabilities the backend already has are offered on top: a digest it keeps
beside every object, a lasting public address, and a signed address that expires.
Visibility is not among them this version — the store's access model has no
single "who may read this" answer to map onto, so asking for one, or naming a
visibility in a write, raises :class:`~xtr_storage.exception.FeatureNotSupportedError`
rather than pretending.

Constructing an adapter imports nothing and opens nothing: ``gcsfs`` is imported,
and the client built, only when the first operation is awaited, so an application
may declare a storage it never touches without paying for a backend it never uses.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final, final
from urllib.parse import quote

from typing_extensions import override

from xtr_storage.adapter._object_store import (
    directory_exists,
    directory_marker,
    is_directory_marker,
    select_allowed,
)
from xtr_storage.adapter.fsspec_adapter import FsspecAdapter
from xtr_storage.config import Config
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    FeatureNotSupportedError,
    MissingBackendError,
    UnableToCheckDirectoryExistenceError,
    UnableToCreateDirectoryError,
    UnableToGenerateTemporaryUrlError,
    UnableToProvideChecksumError,
)
from xtr_storage.feature import Feature
from xtr_storage.path.path_prefixer import PathPrefixer

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Awaitable, Callable, Mapping
    from types import ModuleType

    from fsspec import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information; imported only to type the filesystem built below
        AbstractFileSystem,
    )

    from xtr_storage.mime_type.mime_type_detector_interface import MimeTypeDetectorInterface

__all__ = ["GcsAdapter"]

_DEFAULT_PUBLIC_URL_BASE: Final = "https://storage.googleapis.com"
"""Where an object is reachable from when no emulator endpoint was given."""

_MD5_ALGORITHM: Final = "md5"
_CRC32C_ALGORITHM: Final = "crc32c"

_DIRECT_WRITE_OPTIONS: Final = ("content_type", "metadata")
"""Write settings ``gcsfs`` takes as keyword arguments of their own."""

_FIXED_KEY_WRITE_OPTIONS: Final = (
    "cache_control",
    "content_encoding",
    "content_disposition",
    "content_language",
)
"""Write settings ``gcsfs`` takes grouped under its ``fixed_key_metadata`` argument."""

_WRITE_OPTION_KEYS: Final = frozenset((*_DIRECT_WRITE_OPTIONS, *_FIXED_KEY_WRITE_OPTIONS))
"""Every write option this adapter forwards; anything else a call names is dropped."""


@final
class GcsAdapter(FsspecAdapter):
    """Files in a Google Cloud Storage bucket, behind the shared adapter contract.

    The bucket, and an optional key prefix within it, are the root every path is
    placed under. Directories are the object-store fiction the shared helpers
    keep up; checksums, public URLs and signed URLs are real; visibility is
    refused, because the store offers no single answer to map onto.

    Satisfies the checksum, public-url and temporary-url capability protocols
    structurally — by having their methods, not by inheriting them — so a
    storage discovers each at runtime.
    """

    _bucket: str
    _key_prefixer: PathPrefixer
    _project: str | None
    _token: str | None
    _endpoint_url: str | None
    _default_write_options: dict[str, object]

    def __init__(  # noqa: PLR0913 -- a bucket adapter is configured by many independent, optional knobs (project, token, endpoint, write defaults, detector); none belongs grouped with another
        self,
        bucket: str,
        prefix: str = "",
        *,
        project: str | None = None,
        token: str | None = None,
        endpoint_url: str | None = None,
        write_options: Mapping[str, object] | None = None,
        mime_type_detector: MimeTypeDetectorInterface | None = None,
    ) -> None:
        """Remember where and how to reach the bucket, and open nothing yet.

        Args:
            bucket: The bucket every path lives in.
            prefix: A key prefix within the bucket that the caller never sees,
                so several storages may share one bucket without colliding.
            project: The Google Cloud project the bucket belongs to, for the
                operations that need one; the backend's own default otherwise.
            token: How the backend authenticates — a path to a credentials file,
                a token, or ``"anon"`` for an unauthenticated emulator.
            endpoint_url: Where to reach the store, for pointing at an emulator;
                the real service otherwise.
            write_options: Settings every write forwards unless a call overrides
                them — a content type, a cache-control header, custom metadata.
            mime_type_detector: How a media type is guessed from a name when the
                object carries none; a name-only detector by default.
        """
        stripped_bucket = bucket.strip("/")
        stripped_prefix = prefix.strip("/")
        root = f"{stripped_bucket}/{stripped_prefix}" if stripped_prefix else stripped_bucket
        super().__init__(root, mime_type_detector=mime_type_detector)
        self._bucket = stripped_bucket
        self._key_prefixer = PathPrefixer(stripped_prefix)
        self._project = project
        self._token = token
        self._endpoint_url = endpoint_url
        self._default_write_options = dict(write_options) if write_options is not None else {}

    @override
    def __repr__(self) -> str:
        """Name the bucket and endpoint, never the token held for the client."""
        return (
            f"{type(self).__name__}(bucket={self._bucket!r}, endpoint_url={self._endpoint_url!r})"
        )

    @override
    def _create_filesystem(self) -> AbstractFileSystem:
        """Import ``gcsfs`` and build a client for the bucket, once, on first use."""
        gcsfs = _import_gcsfs()
        filesystem: AbstractFileSystem = gcsfs.GCSFileSystem(  # pyright: ignore[reportAny] -- gcsfs ships no type information
            asynchronous=True,
            skip_instance_cache=True,
            use_listings_cache=False,
            project=self._project,
            token=self._token,
            endpoint_url=self._endpoint_url,
        )
        return filesystem

    @override
    def _session_closer(self) -> Callable[[AbstractFileSystem], Awaitable[None]] | None:
        """Return the coroutine that shuts the client's session down on close.

        ``gcsfs`` opens an aiohttp session on first use and registers no
        finalizer for it, so an owner must close it or leak the connection. The
        bridge runs this once, on close, and only when a session was ever opened.
        """

        async def close(filesystem: AbstractFileSystem) -> None:
            session = getattr(filesystem, "_session", None)
            if session is not None:
                await session.close()  # pyright: ignore[reportAny] -- gcsfs keeps its aiohttp session here; closing it leaves no dangling connection

        return close

    @override
    def _write_options(self, config: Config) -> Mapping[str, object]:
        """Return the write settings ``gcsfs`` understands, in the shape it wants.

        A call's options win over the storage's defaults, and only the handful
        the backend has a name for survive; of those, a content type and custom
        metadata are keyword arguments of their own, while the header-like
        settings are grouped under the one argument the backend collects them in.
        """
        merged: dict[str, object] = {**self._default_write_options, **config.to_dict()}
        forwarded = select_allowed(merged, _WRITE_OPTION_KEYS)
        options: dict[str, object] = {
            key: forwarded[key] for key in _DIRECT_WRITE_OPTIONS if key in forwarded
        }
        fixed = {key: forwarded[key] for key in _FIXED_KEY_WRITE_OPTIONS if key in forwarded}
        if fixed:
            options["fixed_key_metadata"] = fixed
        return options

    @override
    def _is_hidden_entry(self, path: str) -> bool:
        """Hide the zero-byte object that stands in for a directory in a listing."""
        return is_directory_marker(path)

    @staticmethod
    @override
    def _content_type(info: Mapping[str, object]) -> str | None:
        """Ignore the type the store stamps on every object; trust the name instead.

        The store gives every object a media type, inventing a generic one for a
        write that named none, so reading it back would report that invention for
        a file whose name says nothing. The name-based detector the base falls
        back to is the very source a write records the type from, so what is read
        and what is written agree.
        """
        del info
        return None

    @override
    async def write(self, path: str, contents: bytes, config: Config) -> None:
        """Write ``contents`` at ``path``, refusing a visibility this store cannot keep."""
        self._reject_explicit_visibility(config)
        await super().write(path, contents, config)

    @override
    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        """Write ``path`` from chunks, refusing a visibility this store cannot keep."""
        self._reject_explicit_visibility(config)
        await super().write_stream(path, contents, config)

    @override
    async def create_directory(self, path: str, config: Config) -> None:
        """Write the zero-byte marker that stands in for the directory at ``path``.

        The store has no directories, so an empty one is a key ending in a slash;
        the bucket root always exists, so a request for it does nothing. A
        visibility named for the directory is refused, as it is on a write.
        """
        self._reject_explicit_visibility(config)
        if not self._key_prefixer.prefix_path(path):
            return
        marker = directory_marker(self._prefixer.prefix_path(path))
        try:
            await self._get_bridge().pipe_file(marker, b"")
        except OSError as error:
            raise UnableToCreateDirectoryError(path) from error

    @override
    async def directory_exists(self, path: str) -> bool:
        """Return whether a marker or any key stands under ``path``."""
        location = self._prefixer.prefix_path(path)
        try:
            return await directory_exists(self._get_bridge(), location)
        except OSError as error:
            raise UnableToCheckDirectoryExistenceError(path) from error

    async def checksum(self, path: str, config: Config) -> str:
        """Return the digest the store keeps beside the object at ``path``.

        The store records two: an MD5, handed back as the hex of the base64 the
        store keeps it in, and a CRC32C, handed back in the base64 the store
        keeps it in. Any other algorithm — and an object the store kept no digest
        of the asked-for kind for — is declined, which a storage takes as its cue
        to read the bytes and compute one itself.

        Raises:
            ChecksumAlgorithmNotSupportedError: When the algorithm is neither
                ``"md5"`` nor ``"crc32c"``, or the object carries no such digest.
            UnableToProvideChecksumError: When the store could not be asked.
        """
        algorithm = config.str_option(Config.CHECKSUM_ALGORITHM, _MD5_ALGORITHM)
        if algorithm not in (_MD5_ALGORITHM, _CRC32C_ALGORITHM):
            raise ChecksumAlgorithmNotSupportedError(path, algorithm)
        location = self._prefixer.prefix_path(path)
        try:
            info = await self._get_bridge().info(location)
        except FileNotFoundError as error:
            raise UnableToProvideChecksumError(path, "the file does not exist") from error
        except OSError as error:
            raise UnableToProvideChecksumError(path) from error
        if algorithm == _MD5_ALGORITHM:
            encoded = info.get("md5Hash")
            if not isinstance(encoded, str):
                raise ChecksumAlgorithmNotSupportedError(path, algorithm)
            return base64.b64decode(encoded).hex()
        crc32c = info.get("crc32c")
        if not isinstance(crc32c, str):
            raise ChecksumAlgorithmNotSupportedError(path, algorithm)
        return crc32c

    async def public_url(self, path: str, config: Config) -> str:
        """Return the lasting address of the object at ``path``.

        The address is the emulator endpoint, or the public service, followed by
        the bucket and the object's key, the key percent-escaped but for the
        slashes that structure it.
        """
        del config
        base = self._endpoint_url or _DEFAULT_PUBLIC_URL_BASE
        key = self._key_prefixer.prefix_path(path)
        return f"{base}/{self._bucket}/{quote(key)}"

    async def temporary_url(self, path: str, expires_at: datetime, config: Config) -> str:
        """Return a signed address for ``path``, good until ``expires_at``.

        The deadline is turned into a whole number of seconds from now, never
        below one, and the store signs for that long. Anything the backend
        raises while signing becomes an
        :class:`~xtr_storage.exception.UnableToGenerateTemporaryUrlError`, the
        original kept as its cause.

        Raises:
            UnableToGenerateTemporaryUrlError: When the store could not sign.
        """
        del config
        location = self._prefixer.prefix_path(path)
        expiration = max(1, int((expires_at - datetime.now(UTC)).total_seconds()))
        try:
            return await self._get_bridge().sign(location, expiration)
        except Exception as error:
            # Signing fails in backend-specific ways — no credentials, a refusal,
            # a transport error — and the contract is to report any as one error.
            raise UnableToGenerateTemporaryUrlError(path) from error

    def _reject_explicit_visibility(self, config: Config) -> None:
        """Refuse a call that names a visibility this store has no way to keep.

        Raises:
            FeatureNotSupportedError: When the call named a file or directory
                visibility.
        """
        named = (
            config.visibility_option(Config.VISIBILITY) is not None
            or config.visibility_option(Config.DIRECTORY_VISIBILITY) is not None
        )
        if named:
            raise FeatureNotSupportedError(Feature.VISIBILITY, type(self).__name__)


def _import_gcsfs() -> ModuleType:
    """Return the ``gcsfs`` module, or say which extra installs it.

    Raises:
        MissingBackendError: When ``gcsfs`` is not installed.
    """
    try:
        import gcsfs  # noqa: PLC0415  # pyright: ignore[reportMissingTypeStubs] -- a backend lives behind an extra, imported on first use so a constructor pays for nothing; gcsfs ships no type information
    except ImportError as error:
        raise MissingBackendError("gcsfs", "gcs") from error
    return gcsfs
