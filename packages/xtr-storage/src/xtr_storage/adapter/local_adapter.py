"""Files on the disk of the machine the application runs on."""

from __future__ import annotations

import asyncio
import stat
from pathlib import Path
from typing import TYPE_CHECKING, final

from fsspec.implementations.local import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information; this is the only line in the package that names its local filesystem
    LocalFileSystem,
)
from typing_extensions import override

from xtr_storage.adapter.fsspec_adapter import FsspecAdapter
from xtr_storage.adapter.portable_visibility_converter import PortableVisibilityConverter
from xtr_storage.config import Config
from xtr_storage.exception import (
    SymbolicLinkEncounteredError,
    UnableToCreateDirectoryError,
    UnableToRetrieveMetadataError,
    UnableToSetVisibilityError,
    UnableToWriteFileError,
)
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.link_handling import LinkHandling

if TYPE_CHECKING:
    import os
    from collections.abc import AsyncIterable, Mapping

    from fsspec import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information; imported only to name what this adapter builds
        AbstractFileSystem,
    )

    from xtr_storage.adapter.visibility_converter_interface import VisibilityConverterInterface
    from xtr_storage.mime_type.mime_type_detector_interface import MimeTypeDetectorInterface
    from xtr_storage.storage_attributes import StorageAttributes
    from xtr_storage.visibility import Visibility

__all__ = ["LocalAdapter"]


@final
class LocalAdapter(FsspecAdapter):
    """A directory on this machine, everything under it and nothing above it.

    The three things a real filesystem adds to the shared base are all here.
    Visibility becomes permission bits, through a converter the deployment may
    replace. Directories a write needs on the way are created with the mode that
    converter names rather than whatever the process umask leaves, since a
    storage told to keep its directories private must not depend on the shell
    that started the application. And symbolic links, which could point anywhere
    including outside the directory this storage is rooted in, are either left
    out of listings or refused outright.

    Nothing is touched until the first operation: the root directory is created
    by the first write, so an application may declare a storage for a disk that
    is not mounted yet and pay nothing until it uses it.
    """

    _link_handling: LinkHandling
    _visibility_converter: VisibilityConverterInterface

    def __init__(
        self,
        directory: str | os.PathLike[str],
        *,
        visibility: VisibilityConverterInterface | None = None,
        link_handling: LinkHandling = LinkHandling.DISALLOW,
        mime_type_detector: MimeTypeDetectorInterface | None = None,
    ) -> None:
        """Remember the directory and the rules, and touch the disk for nothing.

        Args:
            directory: The directory every path is relative to. Made absolute
                here — reading the working directory, not the disk — because the
                paths a listing hands back are absolute and the root has to be
                strippable from them again.
            visibility: How a visibility becomes permission bits; the portable
                converter and its defaults when left out.
            link_handling: What a listing does with a symbolic link it meets.
                Refusing by default: a link is rarely meant to be part of a
                storage, and silence about one is worse than a failure.
            mime_type_detector: How a media type is guessed from a name, since a
                filesystem stores none.
        """
        super().__init__(
            Path(directory).absolute().as_posix(),
            mime_type_detector=mime_type_detector,
        )
        self._visibility_converter = visibility or PortableVisibilityConverter()
        self._link_handling = link_handling

    @override
    def _create_filesystem(self) -> AbstractFileSystem:
        """Build the local filesystem, told to make missing parent directories.

        ``skip_instance_cache`` keeps this instance out of fsspec's global
        registry, so two storages rooted in two directories never hand each other
        their filesystem, and closing one leaves the other alone.
        """
        return LocalFileSystem(auto_mkdir=True, skip_instance_cache=True)

    @override
    async def write(self, path: str, contents: bytes, config: Config) -> None:
        """Write the bytes at ``path``, directories and permissions as asked."""
        await self._make_parent_directory(path, config)
        await super().write(path, contents, config)
        await self._apply_file_visibility(path, config)

    @override
    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        """Stream the bytes to ``path``, directories and permissions as asked."""
        await self._make_parent_directory(path, config)
        await super().write_stream(path, contents, config)
        await self._apply_file_visibility(path, config)

    @override
    async def create_directory(self, path: str, config: Config) -> None:
        """Create the directory at ``path`` and its parents, with their own mode.

        The mode comes from the call's directory visibility, or from the
        converter's default for directories when the call named none. Only the
        directories this call creates are given it: one that was already there
        keeps what it had, so creating the same directory twice is not a way to
        change its permissions.
        """
        location = self._prefixer.prefix_path(path)
        try:
            await asyncio.to_thread(_make_directories, location, self._directory_mode(config))
        except OSError as error:
            raise UnableToCreateDirectoryError(path) from error

    @override
    async def visibility(self, path: str) -> FileAttributes:
        """Return who may read what is at ``path``, from its permission bits."""
        location = self._prefixer.prefix_path(path)
        try:
            status = await asyncio.to_thread(Path(location).stat)
        except FileNotFoundError as error:
            raise UnableToRetrieveMetadataError.visibility(
                path, "the file does not exist"
            ) from error
        except OSError as error:
            raise UnableToRetrieveMetadataError.visibility(path) from error
        return FileAttributes(path=path, visibility=self._read_visibility(status))

    @override
    async def set_visibility(self, path: str, visibility: Visibility) -> None:
        """Change the permission bits at ``path`` to the ones ``visibility`` means."""
        location = self._prefixer.prefix_path(path)
        try:
            status = await asyncio.to_thread(Path(location).stat)
            await asyncio.to_thread(Path(location).chmod, self._mode_for(status, visibility))
        except FileNotFoundError as error:
            raise UnableToSetVisibilityError(path, "the file does not exist") from error
        except OSError as error:
            raise UnableToSetVisibilityError(path) from error

    @override
    def _map_entry(self, entry: Mapping[str, object], requested: str) -> StorageAttributes | None:
        """Turn one listing entry into a record, links handled as the storage was told.

        The local filesystem already says whether an entry is a link, so deciding
        here costs nothing: no second look at the disk, and the decision is made
        once for shallow and deep listings alike.

        The decision is a match over every way of handling a link rather than a
        test for one of them, so that the set of answers is visible in one place
        and the type checker holds it to covering all of them.
        """
        if entry.get("islink") is not True:
            return super()._map_entry(entry, requested)
        location = self._prefixer.strip_prefix(str(entry.get("name", ""))).strip("/")
        match self._link_handling:
            case LinkHandling.DISALLOW:
                raise SymbolicLinkEncounteredError(location)
            case LinkHandling.SKIP:
                return None

    async def _make_parent_directory(self, path: str, config: Config) -> None:
        """Create the directories a write needs, with the mode it asked for.

        The filesystem would create them itself — it is built with that turned on
        — but with whatever the process umask leaves behind, which is not a
        decision this library lets the environment make.
        """
        parent = Path(self._prefixer.prefix_path(path)).parent
        try:
            await asyncio.to_thread(
                _make_directories, parent.as_posix(), self._directory_mode(config)
            )
        except OSError as error:
            raise UnableToWriteFileError(path) from error

    async def _apply_file_visibility(self, path: str, config: Config) -> None:
        """Set a freshly written file's permissions, when the call named any.

        A write that said nothing about visibility leaves the file as the
        filesystem made it, rather than quietly imposing one of the two modes:
        the caller made no demand, so there is nothing to enforce.
        """
        visibility = config.visibility_option(Config.VISIBILITY)
        if visibility is None:
            return
        await self.set_visibility(path, visibility)

    def _directory_mode(self, config: Config) -> int:
        """Return the mode the directories of this operation should carry."""
        visibility = config.visibility_option(Config.DIRECTORY_VISIBILITY)
        if visibility is None:
            return self._visibility_converter.default_for_directories()
        return self._visibility_converter.for_directory(visibility)

    def _read_visibility(self, status: os.stat_result) -> Visibility:
        """Read a visibility off one path's status, directories asked separately."""
        mode = stat.S_IMODE(status.st_mode)
        if stat.S_ISDIR(status.st_mode):
            return self._visibility_converter.inverse_for_directory(mode)
        return self._visibility_converter.inverse_for_file(mode)

    def _mode_for(self, status: os.stat_result, visibility: Visibility) -> int:
        """Return the mode ``visibility`` means for a path of this kind."""
        if stat.S_ISDIR(status.st_mode):
            return self._visibility_converter.for_directory(visibility)
        return self._visibility_converter.for_file(visibility)


def _make_directories(location: str, mode: int) -> None:
    """Create ``location`` and every missing directory above it, each with ``mode``.

    The mode is applied with a separate permission change rather than handed to
    the creation call, because the process umask masks bits off the latter: a
    directory asked to be readable by everyone would come out private under a
    strict umask, and the storage's promise would depend on the environment.

    Only the directories this call creates are changed. One that already existed
    is left exactly as it was, so writing a file never silently reopens the
    directory tree above it.

    Raises:
        NotADirectoryError: When ``location`` already exists and is not a
            directory, which no amount of creating will fix.
    """
    target = Path(location)
    missing: list[Path] = []
    candidate = target
    while not candidate.exists():
        missing.append(candidate)
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    if not missing and not target.is_dir():
        raise NotADirectoryError(location)
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True)
        directory.chmod(mode)
