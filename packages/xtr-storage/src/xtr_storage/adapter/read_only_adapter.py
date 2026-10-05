"""An adapter with every way of changing what it holds taken away."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    UnableToCopyFileError,
    UnableToCreateDirectoryError,
    UnableToDeleteDirectoryError,
    UnableToDeleteFileError,
    UnableToGeneratePublicUrlError,
    UnableToGenerateTemporaryUrlError,
    UnableToMoveFileError,
    UnableToSetVisibilityError,
    UnableToWriteFileError,
)
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator
    from datetime import datetime

    from xtr_storage.file_attributes import FileAttributes
    from xtr_storage.storage_attributes import StorageAttributes
    from xtr_storage.visibility import Visibility

__all__ = ["ReadOnlyAdapter"]

_REFUSED: Final = "this storage is read-only"
"""The reason every refused change gives, so one string is all a caller matches."""

_DEFAULT_CHECKSUM_ALGORITHM: Final = "md5"
"""What a checksum is taken with when the options name nothing, as a storage assumes."""


@final
class ReadOnlyAdapter(
    StorageAdapterInterface,
    ChecksumProviderInterface,
    PublicUrlGeneratorInterface,
    TemporaryUrlGeneratorInterface,
):
    """Another adapter, published without any of its ways of changing anything.

    What an application hands out when a backend is someone else's to write:
    an archive it may serve but not amend, a bucket another service owns, a
    directory of assets a build step fills. Every read goes through untouched
    and every attempt to change something fails at once, so a mistake surfaces
    here rather than as a permission error from the backend hours later — or,
    worse, as a write that succeeded where it should not have.

    Each refusal is the failure of the operation that was asked for, with the
    reason naming why, so code that already handles "the write did not happen"
    needs nothing new to handle this.

    The three capabilities a backend may have — a digest it keeps, a lasting
    address, a signed one — are read-only themselves, so they are passed on
    when the wrapped adapter has them. This adapter answers to all three
    regardless, because whether the one underneath does is not known until it
    is there; when it does not, each says so in the terms of that capability:
    a checksum reports that no such digest is kept, which is a storage's cue to
    read the file and compute one, and the two url capabilities refuse.
    """

    _inner: StorageAdapterInterface

    def __init__(self, inner: StorageAdapterInterface) -> None:
        """Wrap ``inner`` and keep only the half of it that reads.

        Args:
            inner: The adapter that holds the files. It is never asked to
                change anything, so it may well be one whose credentials
                could.
        """
        self._inner = inner

    @override
    async def file_exists(self, path: str) -> bool:
        """Return whether a file is at ``path``, as the wrapped adapter sees it."""
        return await self._inner.file_exists(path)

    @override
    async def directory_exists(self, path: str) -> bool:
        """Return whether a directory is at ``path``, as the wrapped adapter sees it."""
        return await self._inner.directory_exists(path)

    @override
    async def read(self, path: str) -> bytes:
        """Return the whole file at ``path``."""
        return await self._inner.read(path)

    @override
    def read_stream(self, path: str) -> AsyncIterator[bytes]:
        """Return the file at ``path`` in chunks, straight from the wrapped adapter."""
        return self._inner.read_stream(path)

    @override
    def list_contents(self, path: str, deep: bool) -> AsyncIterator[StorageAttributes]:
        """Return what is under ``path``, straight from the wrapped adapter."""
        return self._inner.list_contents(path, deep)

    @override
    async def visibility(self, path: str) -> FileAttributes:
        """Return who may read the file at ``path``."""
        return await self._inner.visibility(path)

    @override
    async def mime_type(self, path: str) -> FileAttributes:
        """Return what the file at ``path`` holds."""
        return await self._inner.mime_type(path)

    @override
    async def last_modified(self, path: str) -> FileAttributes:
        """Return when the file at ``path`` last changed."""
        return await self._inner.last_modified(path)

    @override
    async def file_size(self, path: str) -> FileAttributes:
        """Return how many bytes the file at ``path`` holds."""
        return await self._inner.file_size(path)

    @override
    async def write(self, path: str, contents: bytes, config: Config) -> None:
        """Refuse: nothing is written through a read-only adapter."""
        del contents, config

        raise UnableToWriteFileError(path, _REFUSED)

    @override
    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        """Refuse before a single chunk is read, leaving the source untouched."""
        del contents, config

        raise UnableToWriteFileError(path, _REFUSED)

    @override
    async def delete(self, path: str) -> None:
        """Refuse, even for a path that holds nothing: a delete is a change."""
        raise UnableToDeleteFileError(path, _REFUSED)

    @override
    async def delete_directory(self, path: str) -> None:
        """Refuse: a read-only adapter deletes no tree."""
        raise UnableToDeleteDirectoryError(path, _REFUSED)

    @override
    async def create_directory(self, path: str, config: Config) -> None:
        """Refuse: a read-only adapter makes no directory."""
        del config

        raise UnableToCreateDirectoryError(path, _REFUSED)

    @override
    async def set_visibility(self, path: str, visibility: Visibility) -> None:
        """Refuse: who may read a file is the owning application's to decide."""
        del visibility

        raise UnableToSetVisibilityError(path, _REFUSED)

    @override
    async def move(self, source: str, destination: str, config: Config) -> None:
        """Refuse: a move would both write and delete."""
        del config

        raise UnableToMoveFileError(source, destination, _REFUSED)

    @override
    async def copy(self, source: str, destination: str, config: Config) -> None:
        """Refuse: the destination is under the same read-only adapter."""
        del config

        raise UnableToCopyFileError(source, destination, _REFUSED)

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
            return await self._inner.checksum(path, config)

        raise ChecksumAlgorithmNotSupportedError(
            path,
            config.str_option(Config.CHECKSUM_ALGORITHM, _DEFAULT_CHECKSUM_ALGORITHM),
        )

    @override
    async def public_url(self, path: str, config: Config) -> str:
        """Return the lasting address the wrapped adapter gives ``path``.

        Raises:
            UnableToGeneratePublicUrlError: When the wrapped adapter has no
                address to give.
        """
        if isinstance(self._inner, PublicUrlGeneratorInterface):
            return await self._inner.public_url(path, config)

        raise UnableToGeneratePublicUrlError(path, "the wrapped adapter generates no public url")

    @override
    async def temporary_url(self, path: str, expires_at: datetime, config: Config) -> str:
        """Return the expiring address the wrapped adapter signs for ``path``.

        Raises:
            UnableToGenerateTemporaryUrlError: When the wrapped adapter signs
                nothing.
        """
        if isinstance(self._inner, TemporaryUrlGeneratorInterface):
            return await self._inner.temporary_url(path, expires_at, config)

        raise UnableToGenerateTemporaryUrlError(path, "the wrapped adapter signs no temporary url")

    @override
    async def close(self) -> None:
        """Close the wrapped adapter; a read-only view holds nothing of its own."""
        await self._inner.close()
