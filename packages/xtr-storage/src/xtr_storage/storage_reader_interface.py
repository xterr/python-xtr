"""The half of a storage that only looks."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_storage.directory_listing import DirectoryListing
    from xtr_storage.storage_attributes import StorageAttributes
    from xtr_storage.visibility import Visibility

__all__ = ["StorageReaderInterface"]


@runtime_checkable
class StorageReaderInterface(Protocol):
    """Reads files and tells what is there, without ever changing it.

    Asking for this rather than the whole storage is how a caller says it only
    looks: a template renderer, a download endpoint, a report that walks a
    directory. The type then refuses the write that a later change might
    otherwise slip in.

    Paths are text, relative to the storage's root, separated by ``/`` and
    carrying no leading slash. Every method that reaches a backend is awaited;
    :meth:`list_contents` is not, because it hands back a plan for reading
    rather than the reading itself.
    """

    async def file_exists(self, location: str) -> bool:
        """Return whether a file is at ``location``.

        Args:
            location: Where to look.

        Returns:
            True when a file is there — a directory at that path answers False.

        Raises:
            UnableToCheckFileExistenceError: When the backend could not say.
        """
        ...

    async def directory_exists(self, location: str) -> bool:
        """Return whether a directory is at ``location``.

        Args:
            location: Where to look.

        Returns:
            True when a directory is there — a file at that path answers False.

        Raises:
            UnableToCheckDirectoryExistenceError: When the backend could not say.
        """
        ...

    async def has(self, location: str) -> bool:
        """Return whether anything at all is at ``location``, file or directory.

        Args:
            location: Where to look.

        Returns:
            True when either a file or a directory is there.

        Raises:
            UnableToCheckExistenceError: When the backend could not say.
        """
        ...

    async def read(self, location: str) -> bytes:
        """Return the whole contents of the file at ``location``.

        Args:
            location: The file to read.

        Returns:
            Every byte of it, in memory. Prefer :meth:`read_stream` for a file
            whose size the caller does not control.

        Raises:
            UnableToReadFileError: When the file is missing or unreadable.
        """
        ...

    def read_stream(self, location: str) -> AsyncIterator[bytes]:
        """Return the file's contents in chunks, so its size need not fit in memory.

        Not awaited: the call itself does nothing, and the backend is reached
        as the chunks are taken.

        Args:
            location: The file to read.

        Returns:
            An iterator over the file's bytes, in order, in chunks of whatever
            size the adapter finds efficient.

        Raises:
            UnableToReadFileError: When the file is missing or unreadable —
                raised while iterating, not when calling.
        """
        ...

    def list_contents(
        self, location: str = "", deep: bool = False
    ) -> DirectoryListing[StorageAttributes]:
        """Return what is under ``location``, as a listing that has read nothing yet.

        Not awaited, because nothing has happened: the returned listing can be
        narrowed and transformed first, and reaches the backend only once
        something iterates it.

        Args:
            location: The directory to look in; the storage's root by default.
            deep: Whether to descend into the directories found, rather than
                naming them and stopping.

        Returns:
            A lazy listing of files and directories.

        Raises:
            UnableToListContentsError: When the backend could not be read —
                raised while iterating, not when calling.
        """
        ...

    async def last_modified(self, path: str) -> int:
        """Return when the file at ``path`` last changed.

        Args:
            path: The file to ask about.

        Returns:
            Whole seconds since the epoch, in UTC.

        Raises:
            UnableToRetrieveMetadataError: When the backend does not know.
        """
        ...

    async def file_size(self, path: str) -> int:
        """Return the size of the file at ``path``.

        Args:
            path: The file to ask about.

        Returns:
            Its size in bytes.

        Raises:
            UnableToRetrieveMetadataError: When the backend does not know, or
                ``path`` names a directory.
        """
        ...

    async def mime_type(self, path: str) -> str:
        """Return what the file at ``path`` holds.

        Args:
            path: The file to ask about.

        Returns:
            A media type such as ``"image/svg+xml"``, from what the backend
            stored alongside the file or, failing that, from its extension.

        Raises:
            UnableToRetrieveMetadataError: When neither says.
        """
        ...

    async def visibility(self, path: str) -> Visibility:
        """Return who may read the file at ``path``.

        Args:
            path: The file to ask about.

        Returns:
            The visibility the backend reports.

        Raises:
            UnableToRetrieveMetadataError: When the backend does not know.
            FeatureNotSupportedError: When the backend has no notion of
                visibility at all.
        """
        ...
