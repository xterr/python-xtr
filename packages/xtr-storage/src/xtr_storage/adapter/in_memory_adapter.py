"""A storage whose files live in a dictionary and vanish with the process.

What a test suite reaches for — nothing to create beforehand, nothing to clean
up after — and what an application uses when a storage is only somewhere to
hand bytes between two steps of one request.

Two things this adds to the shared base. Each adapter gets a dictionary of its
own, because the underlying memory filesystem shares one across every instance
by default, which would let two storages that have nothing to do with each
other read and overwrite each other's files. And visibility, which a dictionary
of bytes has no place for, is kept beside the files in a mapping of its own, so
setting it, reading it, copying it and moving it behave as they would on a
backend that stores it for real.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from fsspec.implementations.memory import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information
    MemoryFileSystem,
)
from typing_extensions import override

from xtr_storage.adapter.fsspec_adapter import FsspecAdapter
from xtr_storage.config import Config
from xtr_storage.exception import UnableToSetVisibilityError
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterable

    from fsspec import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information
        AbstractFileSystem,
    )

    from xtr_storage.mime_type.mime_type_detector_interface import MimeTypeDetectorInterface

__all__ = ["InMemoryAdapter"]


@final
class InMemoryAdapter(FsspecAdapter):
    """Files in a dictionary, each with a visibility remembered beside it.

    Every file this adapter is given is readable from it and from nowhere else:
    two adapters in one process share no store, so a test that writes has
    nothing to undo and cannot colour the next one.

    Visibility is real here rather than refused. There is no permission to set
    on a dictionary entry, so the answer is simply remembered: a write records
    what its options asked for, or the adapter's default where they asked for
    nothing; a copy and a move carry it across; a delete forgets it, as does
    deleting a directory for everything beneath it.
    """

    _default_visibility: Visibility
    _visibility: dict[str, Visibility]

    def __init__(
        self,
        default_visibility: Visibility = Visibility.PUBLIC,
        *,
        mime_type_detector: MimeTypeDetectorInterface | None = None,
    ) -> None:
        """Take the visibility a write falls back on, and hold no store yet.

        Args:
            default_visibility: What a file is worth when nothing said
                otherwise — readable by anyone, matching the openness of a
                store that only this process can reach anyway.
            mime_type_detector: How a media type is guessed from a name; a
                name-only detector by default.
        """
        super().__init__(mime_type_detector=mime_type_detector)
        self._default_visibility = default_visibility
        self._visibility = {}

    @override
    def __repr__(self) -> str:
        """Name the default visibility; an in-memory store holds no secret."""
        return f"{type(self).__name__}(default_visibility={self._default_visibility!r})"

    @override
    def _create_filesystem(self) -> AbstractFileSystem:
        """Build a memory filesystem whose files are this adapter's alone.

        The store and the directory list are class-wide on the filesystem, so
        fresh ones are put on the instance; skipping the instance cache stops a
        second adapter being handed the first one back.
        """
        filesystem = MemoryFileSystem(skip_instance_cache=True)
        filesystem.store = {}
        filesystem.pseudo_dirs = [""]
        return filesystem

    @override
    async def write(self, path: str, contents: bytes, config: Config) -> None:
        """Write ``contents`` at ``path`` and remember who may read it."""
        visibility = self._requested_visibility(config)
        await super().write(path, contents, config)
        self._visibility[_key(path)] = visibility

    @override
    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        """Write ``path`` from chunks and remember who may read it."""
        visibility = self._requested_visibility(config)
        await super().write_stream(path, contents, config)
        self._visibility[_key(path)] = visibility

    @override
    async def move(self, source: str, destination: str, config: Config) -> None:
        """Move the file, and leave no visibility behind at the old path.

        The base has already given the destination the visibility the rule
        calls for — the one the call named, or the source's — by the time this
        drops the source's, so what travelled is kept and what stayed is gone.
        """
        source_key = _key(source)
        await super().move(source, destination, config)
        if source_key != _key(destination):
            _ = self._visibility.pop(source_key, None)

    @override
    async def delete(self, path: str) -> None:
        """Delete the file at ``path`` and forget who could read it."""
        await super().delete(path)
        _ = self._visibility.pop(_key(path), None)

    @override
    async def delete_directory(self, path: str) -> None:
        """Delete the directory and forget the visibility of everything under it."""
        await super().delete_directory(path)
        directory = _key(path)
        # The base refuses an empty path, so a directory is always named here.
        under = f"{directory}/"
        self._visibility = {
            key: visibility
            for key, visibility in self._visibility.items()
            if key != directory and not key.startswith(under)
        }

    @override
    async def visibility(self, path: str) -> FileAttributes:
        """Return who may read the file at ``path``.

        Raises:
            UnableToRetrieveMetadataError: When no file is stored there.
        """
        _ = await self._info(path, "visibility")
        return FileAttributes(
            path=path,
            visibility=self._visibility.get(_key(path), self._default_visibility),
        )

    @override
    async def set_visibility(self, path: str, visibility: Visibility) -> None:
        """Record who may read the file at ``path``.

        Raises:
            UnableToSetVisibilityError: When no file is stored there. A
                remembered answer about a file that does not exist would
                outlive nothing and mislead the next write.
        """
        if not await self.file_exists(path):
            raise UnableToSetVisibilityError(path, "no file is stored there")
        self._visibility[_key(path)] = visibility

    def _requested_visibility(self, config: Config) -> Visibility:
        """Return the visibility a write's options ask for, or the adapter's own."""
        requested = config.visibility_option(Config.VISIBILITY)
        return requested if requested is not None else self._default_visibility


def _key(path: str) -> str:
    """Return the name a path is remembered under, so one file has one entry."""
    return path.strip("/")
