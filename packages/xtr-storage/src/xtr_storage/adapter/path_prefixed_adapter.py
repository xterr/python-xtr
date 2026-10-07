"""An adapter that keeps another one's files under a path of its own."""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    InvalidArgumentError,
    StorageOperationFailedError,
    UnableToCheckExistenceError,
    UnableToCopyFileError,
    UnableToCreateDirectoryError,
    UnableToDeleteDirectoryError,
    UnableToDeleteFileError,
    UnableToGeneratePublicUrlError,
    UnableToGenerateTemporaryUrlError,
    UnableToListContentsError,
    UnableToMoveFileError,
    UnableToReadFileError,
    UnableToRetrieveMetadataError,
    UnableToSetVisibilityError,
    UnableToWriteFileError,
)
from xtr_storage.path.path_prefixer import PathPrefixer
from xtr_storage.path.whitespace_path_normalizer import WhitespacePathNormalizer
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Generator
    from datetime import datetime

    from xtr_storage.file_attributes import FileAttributes
    from xtr_storage.storage_attributes import StorageAttributes
    from xtr_storage.visibility import Visibility

__all__ = ["PathPrefixedAdapter"]

_DEFAULT_CHECKSUM_ALGORITHM: Final = "md5"
"""What a checksum is taken with when the options name nothing, as a storage assumes."""


@final
class PathPrefixedAdapter(
    StorageAdapterInterface,
    ChecksumProviderInterface,
    PublicUrlGeneratorInterface,
    TemporaryUrlGeneratorInterface,
):
    """Another adapter, shown as if its files began one path further down.

    Two applications sharing a bucket, one tenant per directory, a test suite
    that wants its own corner of a real backend: each is the same need, to hand
    out a storage whose root is somewhere inside another one. The caller works
    in plain paths and never learns the prefix, which is what makes the prefix
    changeable — it is configuration, not something spelled out at every call
    site and impossible to move later.

    The translation goes both ways, and both halves matter. Paths go down with
    the prefix on. Listings come back with it off, because an entry a caller
    cannot pass back to the same storage is worse than no entry. And a failure
    the wrapped adapter raises is told again about the path the caller used,
    keeping the original as its ``__cause__`` so the prefixed path is still
    there for whoever is debugging the backend.

    Only the failures of an operation are retold that way. Anything else — a
    capability the backend does not have, an argument that makes no sense —
    passes through as it is: it is not about a path.
    """

    _inner: StorageAdapterInterface
    _prefixer: PathPrefixer

    def __init__(self, inner: StorageAdapterInterface, prefix: str) -> None:
        """Wrap ``inner`` so everything it is asked for sits under ``prefix``.

        Args:
            inner: The adapter that holds the files, under whatever root of its
                own it already has.
            prefix: The path this adapter's root is at, inside ``inner``.

        Raises:
            InvalidArgumentError: When ``prefix`` names no path. A prefix that
                prefixes nothing would make this a pass-through, and a storage
                quietly writing to a shared root instead of its own corner is
                the kind of mistake that is found by finding the files.
            PathTraversalDetectedError: When ``prefix`` carries a ``..`` segment.
            CorruptedPathDetectedError: When ``prefix`` carries a control
                character.
        """
        normalized = WhitespacePathNormalizer(
            allow_relative_path_traversal=False,
        ).normalize_path(prefix)
        if normalized == "":
            raise InvalidArgumentError("the storage prefix must name a path")

        self._inner = inner
        self._prefixer = PathPrefixer(normalized)

    @override
    def __repr__(self) -> str:
        """Name the prefix and the wrapped adapter; neither carries a secret."""
        return f"{type(self).__name__}({self._inner!r}, prefix={self._prefixer.prefix_path('')!r})"

    def _prefixed(self, path: str) -> str:
        """Put ``path`` under the prefix, in the shape an adapter is handed paths in.

        The root itself arrives as the empty path, which prefixing alone would
        turn into a directory path ending in a separator; adapters are given
        paths with no slash at either end, so the join is trimmed back to that.
        """
        return self._prefixer.prefix_path(path).rstrip("/")

    @contextmanager
    def _as_the_caller_asked(
        self,
        source: str,
        destination: str | None = None,
    ) -> Generator[None]:
        """Retell a failure from the wrapped adapter about the paths handed in here.

        Args:
            source: The path the caller named, or the source of a transfer.
            destination: The destination the caller named, for a transfer.
        """
        try:
            yield
        except StorageOperationFailedError as error:
            retold = _about_caller_paths(error, source, destination)
            if retold is None:
                raise

            raise retold from error

    @override
    async def file_exists(self, path: str) -> bool:
        """Return whether a file is at ``path`` under the prefix."""
        with self._as_the_caller_asked(path):
            return await self._inner.file_exists(self._prefixed(path))

    @override
    async def directory_exists(self, path: str) -> bool:
        """Return whether a directory is at ``path`` under the prefix."""
        with self._as_the_caller_asked(path):
            return await self._inner.directory_exists(self._prefixed(path))

    @override
    async def write(self, path: str, contents: bytes, config: Config) -> None:
        """Write ``contents`` at ``path`` under the prefix."""
        with self._as_the_caller_asked(path):
            await self._inner.write(self._prefixed(path), contents, config)

    @override
    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        """Write at ``path`` under the prefix from ``contents``."""
        with self._as_the_caller_asked(path):
            await self._inner.write_stream(self._prefixed(path), contents, config)

    @override
    async def read(self, path: str) -> bytes:
        """Return the whole file at ``path`` under the prefix."""
        with self._as_the_caller_asked(path):
            return await self._inner.read(self._prefixed(path))

    @override
    def read_stream(self, path: str) -> AsyncIterator[bytes]:
        """Return the file at ``path`` under the prefix, in chunks."""
        return self._read_stream(path)

    async def _read_stream(self, path: str) -> AsyncIterator[bytes]:
        """Pass the chunks through, retelling a failure that surfaces mid-read."""
        with self._as_the_caller_asked(path):
            async for chunk in self._inner.read_stream(self._prefixed(path)):
                yield chunk

    @override
    async def delete(self, path: str) -> None:
        """Delete the file at ``path`` under the prefix."""
        with self._as_the_caller_asked(path):
            await self._inner.delete(self._prefixed(path))

    @override
    async def delete_directory(self, path: str) -> None:
        """Delete the directory at ``path`` under the prefix, and its tree."""
        with self._as_the_caller_asked(path):
            await self._inner.delete_directory(self._prefixed(path))

    @override
    async def create_directory(self, path: str, config: Config) -> None:
        """Create the directory at ``path`` under the prefix."""
        with self._as_the_caller_asked(path):
            await self._inner.create_directory(self._prefixed(path), config)

    @override
    async def set_visibility(self, path: str, visibility: Visibility) -> None:
        """Change who may read what is at ``path`` under the prefix."""
        with self._as_the_caller_asked(path):
            await self._inner.set_visibility(self._prefixed(path), visibility)

    @override
    async def visibility(self, path: str) -> FileAttributes:
        """Return who may read the file at ``path``, described at the caller's path."""
        with self._as_the_caller_asked(path):
            return (await self._inner.visibility(self._prefixed(path))).with_path(path)

    @override
    async def mime_type(self, path: str) -> FileAttributes:
        """Return what the file at ``path`` holds, described at the caller's path."""
        with self._as_the_caller_asked(path):
            return (await self._inner.mime_type(self._prefixed(path))).with_path(path)

    @override
    async def last_modified(self, path: str) -> FileAttributes:
        """Return when the file at ``path`` last changed, at the caller's path."""
        with self._as_the_caller_asked(path):
            return (await self._inner.last_modified(self._prefixed(path))).with_path(path)

    @override
    async def file_size(self, path: str) -> FileAttributes:
        """Return how many bytes the file at ``path`` holds, at the caller's path."""
        with self._as_the_caller_asked(path):
            return (await self._inner.file_size(self._prefixed(path))).with_path(path)

    @override
    def list_contents(self, path: str, deep: bool) -> AsyncIterator[StorageAttributes]:
        """Return what is under ``path``, every entry back in the caller's terms."""
        return self._list_contents(path, deep)

    async def _list_contents(self, path: str, deep: bool) -> AsyncIterator[StorageAttributes]:
        """Take the prefix off each entry the wrapped adapter yields."""
        with self._as_the_caller_asked(path):
            async for entry in self._inner.list_contents(self._prefixed(path), deep):
                yield entry.with_path(self._prefixer.strip_prefix(entry.path))

    @override
    async def move(self, source: str, destination: str, config: Config) -> None:
        """Move ``source`` to ``destination``, both under the prefix."""
        with self._as_the_caller_asked(source, destination):
            await self._inner.move(
                self._prefixed(source),
                self._prefixed(destination),
                config,
            )

    @override
    async def copy(self, source: str, destination: str, config: Config) -> None:
        """Copy ``source`` to ``destination``, both under the prefix."""
        with self._as_the_caller_asked(source, destination):
            await self._inner.copy(
                self._prefixed(source),
                self._prefixed(destination),
                config,
            )

    @override
    async def checksum(self, path: str, config: Config) -> str:
        """Return the digest the wrapped adapter keeps for ``path``, if it keeps one.

        Raises:
            ChecksumAlgorithmNotSupportedError: When the wrapped adapter keeps
                no digest at all — the same answer it would give for an
                algorithm it does not hold, and what makes a storage read the
                file and compute the digest itself.
        """
        if isinstance(self._inner, ChecksumProviderInterface):
            return await self._inner.checksum(self._prefixed(path), config)

        raise ChecksumAlgorithmNotSupportedError(
            path,
            config.str_option(Config.CHECKSUM_ALGORITHM, _DEFAULT_CHECKSUM_ALGORITHM),
        )

    @override
    async def public_url(self, path: str, config: Config) -> str:
        """Return the lasting address the wrapped adapter gives the prefixed path.

        Raises:
            UnableToGeneratePublicUrlError: When the wrapped adapter has no
                address to give.
        """
        if isinstance(self._inner, PublicUrlGeneratorInterface):
            return await self._inner.public_url(self._prefixed(path), config)

        raise UnableToGeneratePublicUrlError(path, "the wrapped adapter generates no public url")

    @override
    async def temporary_url(self, path: str, expires_at: datetime, config: Config) -> str:
        """Return the expiring address the wrapped adapter signs for the prefixed path.

        Raises:
            UnableToGenerateTemporaryUrlError: When the wrapped adapter signs
                nothing.
        """
        if isinstance(self._inner, TemporaryUrlGeneratorInterface):
            return await self._inner.temporary_url(self._prefixed(path), expires_at, config)

        raise UnableToGenerateTemporaryUrlError(path, "the wrapped adapter signs no temporary url")

    @override
    async def close(self) -> None:
        """Close the wrapped adapter; a prefix holds nothing of its own."""
        await self._inner.close()


def _about_caller_paths(
    error: StorageOperationFailedError,
    source: str,
    destination: str | None,
) -> StorageOperationFailedError | None:
    """Rebuild ``error`` around the paths a caller used, or answer ``None``.

    A failure composes its message from the paths it was given, so there is
    nothing generic to rewrite: the only way to move one onto other paths is to
    build the same class again from its own fields. Each shape of failure this
    library defines is handled below, and one it does not know is answered with
    ``None`` — left exactly as the wrapped adapter raised it, since guessing at
    an unknown constructor would lose what it carried.

    Args:
        error: What the wrapped adapter raised, about prefixed paths.
        source: The path the caller named, or the source of a transfer.
        destination: The destination the caller named, for a transfer.

    Returns:
        The same failure about the caller's paths, or ``None`` when its shape
        is not one of the known ones.
    """
    if isinstance(error, (UnableToMoveFileError, UnableToCopyFileError)):
        return type(error)(
            source,
            destination if destination is not None else error.destination,
            error.reason,
        )

    if isinstance(error, UnableToRetrieveMetadataError):
        return type(error)(source, error.metadata_type, error.reason)

    if isinstance(error, UnableToListContentsError):
        return type(error)(source, deep=error.deep)

    if isinstance(error, UnableToCheckExistenceError):
        return type(error)(source)

    if isinstance(
        error,
        (
            UnableToReadFileError,
            UnableToWriteFileError,
            UnableToDeleteFileError,
            UnableToDeleteDirectoryError,
            UnableToCreateDirectoryError,
            UnableToSetVisibilityError,
        ),
    ):
        return type(error)(source, error.reason)

    return None
