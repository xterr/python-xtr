"""Files on the disk of the machine the application runs on."""

from __future__ import annotations

import asyncio
import os
import stat
from pathlib import Path
from typing import TYPE_CHECKING, Final, final

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
from xtr_storage.path.path_prefixer import PathPrefixer

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Mapping

    from fsspec import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information; imported only to name what this adapter builds
        AbstractFileSystem,
    )

    from xtr_storage.adapter.visibility_converter_interface import VisibilityConverterInterface
    from xtr_storage.mime_type.mime_type_detector_interface import MimeTypeDetectorInterface
    from xtr_storage.storage_attributes import StorageAttributes
    from xtr_storage.visibility import Visibility

__all__ = ["LocalAdapter"]

_DIRECTORY_FLAGS: Final = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
"""The open flags that reach a directory, a symbolic link in its place followed."""

_NO_FOLLOW_FLAGS: Final = _DIRECTORY_FLAGS | getattr(os, "O_NOFOLLOW", 0)
"""The same, refusing a symbolic link in the directory's place."""


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

    Staying inside the root is enforced on every operation, not only on
    listings, and under either way of handling a link: each caller path is
    resolved through the filesystem before the backend is reached, and one that
    a link — its own last segment, or a directory on the way — carries outside
    the root is refused with
    :class:`~xtr_storage.exception.SymbolicLinkEncounteredError`, because such a
    path names a file the storage does not answer for. Skipping links decides
    what a listing shows; it does not make the tree above the root reachable
    through one.

    Nothing is touched until the first operation: the root directory is created
    by the first write, so an application may declare a storage for a disk that
    is not mounted yet and pay nothing until it uses it.
    """

    _link_handling: LinkHandling
    _visibility_converter: VisibilityConverterInterface
    _root: str

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
                strippable from them again. One that is itself a symbolic link
                is honoured — the link is the operator's own choice — and only
                links met below it are refused.
            visibility: How a visibility becomes permission bits; the portable
                converter and its defaults when left out.
            link_handling: What an operation does with a symbolic link it meets.
                Refusing by default: a link is rarely meant to be part of a
                storage, and silence about one is worse than a failure. Either
                way, no link is followed out of the root.
            mime_type_detector: How a media type is guessed from a name, since a
                filesystem stores none.
        """
        root = Path(directory).absolute().as_posix()
        super().__init__(root, mime_type_detector=mime_type_detector)
        self._prefixer = _RootedPathPrefixer(root)
        self._root = root
        self._visibility_converter = visibility or PortableVisibilityConverter()
        self._link_handling = link_handling

    @override
    def __repr__(self) -> str:
        """Name the root and how links are handled; a local adapter holds no secret."""
        return f"{type(self).__name__}(root={self._root!r}, link_handling={self._link_handling!r})"

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
            await asyncio.to_thread(
                _make_directories, self._root, location, self._directory_mode(config)
            )
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
                _make_directories, self._root, parent.as_posix(), self._directory_mode(config)
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


@final
class _RootedPathPrefixer(PathPrefixer):
    """A prefixer that refuses a path a symbolic link carries outside the root.

    The local adapter turns a caller path into a backend location in exactly one
    place — this prefixer — so guarding here guards every operation at once: a
    read, a write, a delete, a move, a copy or a metadata lookup all pass their
    path through :meth:`prefix_path` (or :meth:`prefix_directory_path`) before the
    backend is reached. The resolved location is required to stay at or below the
    root; one a link resolves to elsewhere is refused, because it names a file
    the storage does not hold. This holds whatever the adapter was told to do
    with links: that setting decides what a listing shows, and a link left out
    of a listing must not be a way in through the back. Listings keep their own
    per-entry link handling, which sees links the prefix never resolves.
    """

    def __init__(self, root: str) -> None:
        """Remember the root every resolved path has to stay within."""
        super().__init__(root)
        self._root = root

    @override
    def prefix_path(self, path: str) -> str:
        """Place ``path`` under the root, refusing one a link carries outside it."""
        location = super().prefix_path(path)
        self._refuse_escape(path, location)
        return location

    @override
    def prefix_directory_path(self, path: str) -> str:
        """Place a directory ``path`` under the root, refusing a link escape."""
        location = super().prefix_directory_path(path)
        self._refuse_escape(path, location)
        return location

    def _refuse_escape(self, path: str, location: str) -> None:
        """Raise when ``location`` resolves outside the root.

        Both sides are resolved through the filesystem so that a root reached by
        a link of its own — ``/var`` standing for ``/private/var`` and the like —
        is compared like with like, and only a path that genuinely leaves the
        tree is refused.

        Raises:
            SymbolicLinkEncounteredError: When the resolved path is outside the
                root.
        """
        real = os.path.realpath(location)
        root = os.path.realpath(self._root)
        if real != root and not real.startswith(root + os.sep):
            raise SymbolicLinkEncounteredError(path.strip("/"))


def _make_directories(root: str, location: str, mode: int) -> None:
    """Create ``location`` and every missing directory down from ``root``, each ``mode``.

    The chain below the root is walked one component at a time, each opened with
    ``O_NOFOLLOW`` so a symbolic link planted on the way redirects nothing: the
    creation stays inside the root or fails. The mode is applied with a separate
    permission change rather than handed to the creation call, because the
    process umask masks bits off the latter.

    The root itself is opened following links, because it is the operator's own
    choice and is often a link by design — ``/var`` standing for
    ``/private/var``, a release directory a deploy repoints. Refusing it would
    make every write and every directory creation fail on such a root. What a
    link may not do is appear *below* the root and carry the tree elsewhere,
    which is what the walk refuses.

    Only the directories this call creates are changed, and only those at or
    below the root: one that already existed is left exactly as it was, and an
    ancestor above the root that had to be made is created but not re-permissioned.

    Raises:
        NotADirectoryError: When the root already exists and is not a directory,
            which no amount of creating will fix.
    """
    root_path = Path(root)
    _ensure_root(root_path, mode)
    descriptor = os.open(root, _DIRECTORY_FLAGS)
    try:
        for part in Path(location).relative_to(root_path).parts:
            child = _descend(descriptor, part, mode)
            os.close(descriptor)
            descriptor = child
    finally:
        os.close(descriptor)


def _ensure_root(root: Path, mode: int) -> None:
    """Create the root and any missing ancestor, giving ``mode`` to the root alone."""
    missing: list[Path] = []
    candidate = root
    while not candidate.exists():
        missing.append(candidate)
        parent = candidate.parent
        if parent == candidate:
            break
        candidate = parent
    if not missing and not root.is_dir():
        raise NotADirectoryError(str(root))
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True)
        if directory == root:
            directory.chmod(mode)


def _descend(parent_fd: int, name: str, mode: int) -> int:
    """Open ``name`` under ``parent_fd`` without following a link, creating it if missing.

    A freshly created directory is given ``mode``; an existing one is left alone.
    ``parent_fd`` stays open and stays the caller's: the walk closes it once the
    child is in hand. Closing it here as well would close it twice whenever this
    descent failed — and a second close is not merely wasteful, it answers
    ``EBADF`` over the real error and can land on a descriptor another thread has
    been handed in the meantime.

    Raises:
        OSError: When ``name`` is a symbolic link (``O_NOFOLLOW`` refuses it) or
            exists as something other than a directory.
    """
    try:
        os.mkdir(name, dir_fd=parent_fd)
        created = True
    except FileExistsError:
        created = False
    descriptor = os.open(name, _NO_FOLLOW_FLAGS, dir_fd=parent_fd)
    if created:
        try:
            os.fchmod(descriptor, mode)
        except OSError:
            os.close(descriptor)
            raise
    return descriptor
