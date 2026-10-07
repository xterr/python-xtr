"""The half of a storage that changes what is there."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Iterable, Mapping
    from typing import BinaryIO

    from xtr_storage.visibility import Visibility

__all__ = ["StorageWriterInterface"]


@runtime_checkable
class StorageWriterInterface(Protocol):
    """Writes, deletes, moves and copies — everything that leaves a mark.

    The counterpart of :class:`~xtr_storage.StorageReaderInterface`, kept apart
    so an upload handler can be handed the ability to write without being
    handed the ability to read every other file in the storage.

    Each method takes an optional mapping of options which is laid over the
    ones the storage was built with, for that call alone: a visibility, a
    content type, whatever the backend understands. Paths are text, relative to
    the storage's root, separated by ``/``.
    """

    async def write(
        self,
        location: str,
        contents: bytes,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Write ``contents`` at ``location``, replacing whatever was there.

        Missing directories on the way are created.

        Args:
            location: Where the file goes.
            contents: What it holds.
            config: Options for this call alone.

        Raises:
            UnableToWriteFileError: When the backend refused the write.
        """
        ...

    async def write_stream(
        self,
        location: str,
        contents: AsyncIterable[bytes] | Iterable[bytes] | BinaryIO,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Write at ``location`` from a source read in pieces.

        For contents that should not be held in memory at once, and for the
        upload handles a web framework hands over.

        Args:
            location: Where the file goes.
            contents: Chunks to write in order, from an async source, a plain
                iterable, or an open binary file, which is rewound first.
            config: Options for this call alone.

        Raises:
            InvalidStreamError: When ``contents`` is none of the three.
            UnableToWriteFileError: When the backend refused the write.
        """
        ...

    async def set_visibility(self, path: str, visibility: Visibility | str) -> None:
        """Change who may read the file or directory at ``path``.

        Args:
            path: What to change.
            visibility: The visibility to set, or its name.

        Raises:
            InvalidVisibilityError: When the name stands for no visibility.
            UnableToSetVisibilityError: When the backend refused the change.
            FeatureNotSupportedError: When the backend has no notion of
                visibility at all.
        """
        ...

    async def delete(self, location: str) -> None:
        """Delete the file at ``location``.

        Deleting a file that is not there is not an error: the caller asked for
        it to be gone, and it is.

        Args:
            location: The file to delete.

        Raises:
            UnableToDeleteFileError: When the backend refused the deletion.
        """
        ...

    async def delete_directory(self, location: str) -> None:
        """Delete the directory at ``location`` and everything under it.

        A directory that is not there is not an error, for the same reason.

        Args:
            location: The directory to delete.

        Raises:
            UnableToDeleteDirectoryError: When the backend refused the deletion.
        """
        ...

    async def create_directory(
        self,
        location: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Create the directory at ``location``, and the ones leading to it.

        Creating one that already exists is not an error.

        Args:
            location: The directory to create.
            config: Options for this call alone, a directory visibility among
                them.

        Raises:
            UnableToCreateDirectoryError: When the backend refused.
        """
        ...

    async def move(
        self,
        source: str,
        destination: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Move the file at ``source`` to ``destination``, overwriting it.

        Asked to move a file onto itself, nothing is done unless the options say
        otherwise: see :class:`~xtr_storage.IdenticalPathPolicy`.

        Args:
            source: The file to move.
            destination: Where it ends up.
            config: Options for this call alone; what an identical source and
                destination does is one of them.

        Raises:
            UnableToMoveFileError: When the backend refused the move, or the
                two paths are the same and the options say that is a mistake.
        """
        ...

    async def copy(
        self,
        source: str,
        destination: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Copy the file at ``source`` to ``destination``, overwriting it.

        Asked to copy a file onto itself, nothing is done unless the options say
        otherwise: see :class:`~xtr_storage.IdenticalPathPolicy`.

        Args:
            source: The file to copy.
            destination: Where the copy goes.
            config: Options for this call alone; what an identical source and
                destination does is one of them.

        Raises:
            UnableToCopyFileError: When the backend refused the copy, or the
                two paths are the same and the options say that is a mistake.
        """
        ...
