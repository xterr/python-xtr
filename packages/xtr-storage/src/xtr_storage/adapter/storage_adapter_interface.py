"""What every backend has to be able to do."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator

    from xtr_storage.config import Config
    from xtr_storage.file_attributes import FileAttributes
    from xtr_storage.storage_attributes import StorageAttributes
    from xtr_storage.visibility import Visibility

__all__ = ["StorageAdapterInterface"]


@runtime_checkable
class StorageAdapterInterface(Protocol):
    """One backend's side of the bargain: paths in, bytes and facts out.

    This is deliberately narrower than what a storage offers its callers. A
    storage is the front door — it normalizes paths, layers options, refuses
    what it can refuse and falls back where it can. An adapter is handed the
    result of all that: a path already cleaned, and a :class:`~xtr_storage.Config`
    already merged. It never has to guess what a caller meant.

    That is what makes a new backend a small piece of work, and what lets one
    conformance suite judge every backend by the same behaviour.

    Anything a backend genuinely cannot do raises ``FeatureNotSupportedError``
    rather than pretending: a silent no-op would leave a caller believing a
    file is private when anyone can read it.

    The three metadata methods return :class:`~xtr_storage.FileAttributes`
    rather than the bare value, so an adapter that learned four facts from one
    round trip can hand all four back and let the storage keep what it needs.
    """

    async def file_exists(self, path: str) -> bool:
        """Return whether a file — not a directory — is at ``path``.

        Raises:
            UnableToCheckFileExistenceError: When the backend could not say.
        """
        ...

    async def directory_exists(self, path: str) -> bool:
        """Return whether a directory — not a file — is at ``path``.

        Raises:
            UnableToCheckDirectoryExistenceError: When the backend could not say.
        """
        ...

    async def write(self, path: str, contents: bytes, config: Config) -> None:
        """Write ``contents`` at ``path``, making the directories on the way.

        Args:
            path: Where the file goes.
            contents: What it holds.
            config: The options in force, a visibility and a content type
                among the ones an adapter may read.

        Raises:
            UnableToWriteFileError: When the backend refused the write.
        """
        ...

    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        """Write at ``path`` from chunks, without holding the whole file in memory.

        Only an async source arrives here: a storage has already turned an open
        file or a plain iterable into one.

        Args:
            path: Where the file goes.
            contents: The chunks, in order.
            config: The options in force.

        Raises:
            UnableToWriteFileError: When the backend refused the write.
        """
        ...

    async def read(self, path: str) -> bytes:
        """Return the whole contents of the file at ``path``.

        Raises:
            UnableToReadFileError: When the file is missing or unreadable.
        """
        ...

    def read_stream(self, path: str) -> AsyncIterator[bytes]:
        """Return the file's contents in chunks, reaching the backend as they are taken.

        Not awaited, so an adapter may implement it as an async generator.

        Raises:
            UnableToReadFileError: While iterating, when the file is missing or
                unreadable.
        """
        ...

    async def delete(self, path: str) -> None:
        """Delete the file at ``path``, treating a missing file as already deleted.

        Raises:
            UnableToDeleteFileError: When the backend refused the deletion.
        """
        ...

    async def delete_directory(self, path: str) -> None:
        """Delete the directory at ``path`` and everything under it.

        A directory that is not there is already deleted.

        Raises:
            UnableToDeleteDirectoryError: When the backend refused the deletion.
        """
        ...

    async def create_directory(self, path: str, config: Config) -> None:
        """Create the directory at ``path``, and the ones leading to it.

        Args:
            path: The directory to create.
            config: The options in force, a directory visibility among them.

        Raises:
            UnableToCreateDirectoryError: When the backend refused.
        """
        ...

    async def set_visibility(self, path: str, visibility: Visibility) -> None:
        """Change who may read what is at ``path``.

        Raises:
            UnableToSetVisibilityError: When the backend refused the change.
            FeatureNotSupportedError: When the backend has no notion of
                visibility at all.
        """
        ...

    async def visibility(self, path: str) -> FileAttributes:
        """Return who may read the file at ``path``, as an attributes record.

        Raises:
            UnableToRetrieveMetadataError: When the backend does not know.
            FeatureNotSupportedError: When the backend has no notion of
                visibility at all.
        """
        ...

    async def mime_type(self, path: str) -> FileAttributes:
        """Return what the file at ``path`` holds, as an attributes record.

        Raises:
            UnableToRetrieveMetadataError: When neither the backend nor the
                file's name says.
        """
        ...

    async def last_modified(self, path: str) -> FileAttributes:
        """Return when the file at ``path`` last changed, as an attributes record.

        Raises:
            UnableToRetrieveMetadataError: When the backend does not know.
        """
        ...

    async def file_size(self, path: str) -> FileAttributes:
        """Return the size of the file at ``path``, as an attributes record.

        Raises:
            UnableToRetrieveMetadataError: When the backend does not know, or
                ``path`` names a directory.
        """
        ...

    def list_contents(self, path: str, deep: bool) -> AsyncIterator[StorageAttributes]:
        """Return what is under ``path``, one entry at a time.

        Not awaited, so an adapter may implement it as an async generator and a
        storage may wrap it in a lazy listing. A directory that is not there
        yields nothing rather than raising: a backend where directories are
        only implied cannot tell the two apart.

        Args:
            path: The directory to look in; the adapter's root when empty.
            deep: Whether to descend into the directories found.
        """
        ...

    async def move(self, source: str, destination: str, config: Config) -> None:
        """Move the file at ``source`` to ``destination``, overwriting it.

        Raises:
            UnableToMoveFileError: When the backend refused the move.
        """
        ...

    async def copy(self, source: str, destination: str, config: Config) -> None:
        """Copy the file at ``source`` to ``destination``, overwriting it.

        Raises:
            UnableToCopyFileError: When the backend refused the copy.
        """
        ...

    async def close(self) -> None:
        """Release whatever the adapter holds open, and stay usable afterwards.

        A backend reached over the network keeps a session; one on local disk
        keeps nothing and does nothing here. Closing twice is not an error.
        """
        ...
