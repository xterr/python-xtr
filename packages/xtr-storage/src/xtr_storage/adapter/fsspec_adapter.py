"""The shared base every fsspec-backed adapter grows from.

One filesystem, one root, and the whole adapter contract expressed through the
:class:`~xtr_storage.adapter._fsspec_bridge.FsspecBridge`. A concrete backend is
a small subclass: it says how to build its filesystem — and, where its backend
differs, which of the handful of hooks below to override — while the reading,
writing, listing, moving and metadata logic lives here once.

Constructing an adapter does no work: the filesystem is built, and its session
opened, only when the first operation is awaited, so an application may declare
a dozen storages and touch none of them until a request needs one.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile, SpooledTemporaryFile
from typing import TYPE_CHECKING, Final

from typing_extensions import override

from xtr_storage.adapter._fsspec_bridge import FsspecBridge
from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.config import Config
from xtr_storage.directory_attributes import DirectoryAttributes
from xtr_storage.exception import (
    FeatureNotSupportedError,
    UnableToCheckDirectoryExistenceError,
    UnableToCheckFileExistenceError,
    UnableToCopyFileError,
    UnableToCreateDirectoryError,
    UnableToDeleteDirectoryError,
    UnableToDeleteFileError,
    UnableToMoveFileError,
    UnableToReadFileError,
    UnableToRetrieveMetadataError,
    UnableToWriteFileError,
)
from xtr_storage.feature import Feature
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.mime_type.extension_mime_type_detector import ExtensionMimeTypeDetector
from xtr_storage.path.path_prefixer import PathPrefixer

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Awaitable, Callable, Mapping

    from fsspec import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information; imported only to type the filesystem a subclass builds
        AbstractFileSystem,
    )

    from xtr_storage.mime_type.mime_type_detector_interface import MimeTypeDetectorInterface
    from xtr_storage.storage_attributes import StorageAttributes
    from xtr_storage.visibility import Visibility

__all__ = ["FsspecAdapter"]

CHUNK_SIZE: Final = 1_048_576
"""How much of a file a streamed read pulls at a time: one mebibyte."""

_SPOOL_MAX_SIZE: Final = 8 * 1_048_576
"""How large a streamed write may grow in memory before it spills to disk."""

_LAST_MODIFIED_KEYS: Final = ("mtime", "LastModified", "updated", "created")
"""The keys a backend may keep a file's last-write time under, most specific first."""

_CONTENT_TYPE_KEYS: Final = ("ContentType", "contentType", "content_type")
"""The keys a backend may keep a file's media type under."""


class FsspecAdapter(StorageAdapterInterface, ABC):
    """Everything an fsspec backend does, bar the one line that builds it.

    A subclass implements :meth:`_create_filesystem` and inherits a working
    adapter. Where its backend behaves differently — an object store that has
    no real directories, one that keeps a media type of its own — it overrides
    a hook rather than a whole method: :meth:`_write_options` to forward write
    settings, :meth:`_is_hidden_entry` to hide the markers it lists,
    :meth:`_session_closer` to shut a client down. Visibility is off by default,
    :meth:`visibility` and :meth:`set_visibility` raising until a subclass that
    has it overrides them.
    """

    _bridge: FsspecBridge | None
    _mime_detector: MimeTypeDetectorInterface
    _prefixer: PathPrefixer

    def __init__(
        self,
        root: str = "",
        *,
        mime_type_detector: MimeTypeDetectorInterface | None = None,
    ) -> None:
        """Remember the root and the detector, and open nothing.

        Args:
            root: What every path is stored under — a directory, a key prefix.
                Empty means the backend's own root, so the adapter is a
                pass-through.
            mime_type_detector: How a media type is guessed from a name when the
                backend keeps none; a name-only detector by default.
        """
        self._prefixer = PathPrefixer(root)
        self._mime_detector = mime_type_detector or ExtensionMimeTypeDetector()
        self._bridge = None

    @abstractmethod
    def _create_filesystem(self) -> AbstractFileSystem:
        """Build the filesystem this adapter speaks to.

        Called once, on the first operation, so a subclass may do the import and
        the client setup its backend needs without a bare constructor paying for
        them. The result is wrapped in a bridge and kept for the adapter's life.
        """

    def _get_bridge(self) -> FsspecBridge:
        """Return the bridge, building the filesystem the first time it is asked."""
        if self._bridge is None:
            self._bridge = FsspecBridge(self._create_filesystem(), closer=self._session_closer())
        return self._bridge

    def _write_options(self, config: Config) -> Mapping[str, object]:
        """Return the keyword settings a write forwards to the backend.

        Nothing by default: a plain filesystem takes bytes and a path. An object
        store overrides this to pass a content type, an access list, a storage
        class — whichever of a call's options it understands.
        """
        del config
        return {}

    def _is_hidden_entry(self, path: str) -> bool:
        """Return whether a listed entry is an artefact a caller should not see.

        False for everything by default. An object store that writes a marker
        object to stand in for a directory overrides this to keep that marker
        out of its listings.
        """
        del path
        return False

    def _session_closer(self) -> Callable[[AbstractFileSystem], Awaitable[None]] | None:
        """Return what closes the backend's session, or ``None`` when there is none.

        A synchronous filesystem keeps nothing open; a networked one overrides
        this to hand back the coroutine that shuts its client down, which the
        bridge runs once, on close, only if a session was ever opened.
        """
        return None

    @override
    async def read(self, path: str) -> bytes:
        """Return the whole file at ``path``."""
        location = self._prefixer.prefix_path(path)
        try:
            return await self._get_bridge().cat_file(location)
        except FileNotFoundError as error:
            raise UnableToReadFileError(path, "the file does not exist") from error
        except OSError as error:
            raise UnableToReadFileError(path) from error

    @override
    async def read_stream(self, path: str) -> AsyncIterator[bytes]:
        """Yield the file at ``path`` a mebibyte at a time, reaching back for each."""
        location = self._prefixer.prefix_path(path)
        bridge = self._get_bridge()
        try:
            info = await bridge.info(location)
        except FileNotFoundError as error:
            raise UnableToReadFileError(path, "the file does not exist") from error
        except OSError as error:
            raise UnableToReadFileError(path) from error
        size = info.get("size")
        total = size if isinstance(size, int) else 0
        for start in range(0, total, CHUNK_SIZE):
            end = min(start + CHUNK_SIZE, total)
            try:
                yield await bridge.cat_file(location, start=start, end=end)
            except OSError as error:
                raise UnableToReadFileError(path) from error

    @override
    async def write(self, path: str, contents: bytes, config: Config) -> None:
        """Write ``contents`` at ``path`` in one call."""
        location = self._prefixer.prefix_path(path)
        options = self._write_options(config)
        try:
            await self._get_bridge().pipe_file(location, contents, **options)
        except OSError as error:
            raise UnableToWriteFileError(path) from error

    @override
    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        """Spool ``contents`` to a temporary file, then hand that to the backend."""
        location = self._prefixer.prefix_path(path)
        options = self._write_options(config)
        # A `with` cannot span the awaited helper calls the spool is handed to; the
        # try/finally below closes it on every path instead.
        spooled = SpooledTemporaryFile(max_size=_SPOOL_MAX_SIZE)  # noqa: SIM115
        try:
            async for chunk in contents:
                _ = await asyncio.to_thread(spooled.write, chunk)
            await asyncio.to_thread(spooled.rollover)
            await self._upload_spooled(spooled, location, options)
        except OSError as error:
            raise UnableToWriteFileError(path) from error
        finally:
            await asyncio.to_thread(spooled.close)

    async def _upload_spooled(
        self,
        spooled: SpooledTemporaryFile[bytes],
        location: str,
        options: Mapping[str, object],
    ) -> None:
        """Upload a spooled write, by its own path when it has one, else via a copy.

        A spooled file that has spilled to disk sometimes exposes a real path and
        sometimes only a file descriptor; when the path is usable the backend
        reads it directly, otherwise the bytes are copied to a named temporary
        file first, since ``put_file`` needs a name on disk.
        """
        name = getattr(spooled, "name", None)
        if isinstance(name, str) and await asyncio.to_thread(Path(name).exists):
            await asyncio.to_thread(spooled.flush)
            await self._get_bridge().put_file(name, location, **options)
            return
        await self._upload_via_named_temp(spooled, location, options)

    async def _upload_via_named_temp(
        self,
        spooled: SpooledTemporaryFile[bytes],
        location: str,
        options: Mapping[str, object],
    ) -> None:
        """Copy a spooled write to a named temporary file and upload that."""
        _ = await asyncio.to_thread(spooled.seek, 0)
        with NamedTemporaryFile(delete=False) as handle:
            name = handle.name
            while True:
                chunk = await asyncio.to_thread(spooled.read, CHUNK_SIZE)
                if not chunk:
                    break
                _ = await asyncio.to_thread(handle.write, chunk)
        try:
            await self._get_bridge().put_file(name, location, **options)
        finally:
            await asyncio.to_thread(Path(name).unlink)

    @override
    async def file_exists(self, path: str) -> bool:
        """Return whether a file — not a directory — is at ``path``."""
        try:
            info = await self._get_bridge().info(self._prefixer.prefix_path(path))
        except FileNotFoundError:
            return False
        except OSError as error:
            raise UnableToCheckFileExistenceError(path) from error
        return info.get("type") == "file"

    @override
    async def directory_exists(self, path: str) -> bool:
        """Return whether a directory — not a file — is at ``path``."""
        try:
            info = await self._get_bridge().info(self._prefixer.prefix_path(path))
        except FileNotFoundError:
            return False
        except OSError as error:
            raise UnableToCheckDirectoryExistenceError(path) from error
        return info.get("type") == "directory"

    @override
    async def delete(self, path: str) -> None:
        """Delete the file at ``path``, treating a missing one as already gone."""
        location = self._prefixer.prefix_path(path)
        try:
            await self._get_bridge().rm_file(location)
        except FileNotFoundError:
            return
        except OSError as error:
            raise UnableToDeleteFileError(path) from error

    @override
    async def delete_directory(self, path: str) -> None:
        """Delete the directory at ``path`` and its tree, missing being no failure."""
        location = self._prefixer.prefix_directory_path(path)
        try:
            await self._get_bridge().rm(location, recursive=True)
        except FileNotFoundError:
            return
        except OSError as error:
            raise UnableToDeleteDirectoryError(path) from error

    @override
    async def create_directory(self, path: str, config: Config) -> None:
        """Create the directory at ``path`` and its parents, once being enough."""
        del config
        location = self._prefixer.prefix_path(path)
        try:
            await self._get_bridge().mkdir(location, create_parents=True)
        except FileExistsError:
            return
        except OSError as error:
            raise UnableToCreateDirectoryError(path) from error

    @override
    def list_contents(self, path: str, deep: bool) -> AsyncIterator[StorageAttributes]:
        """Return what is under ``path``, one entry at a time."""
        return self._list_contents(path, deep)

    async def _list_contents(self, path: str, deep: bool) -> AsyncIterator[StorageAttributes]:
        """Walk or list one directory and yield its entries, its own skipped."""
        location = self._prefixer.prefix_directory_path(path)
        requested = path.strip("/")
        bridge = self._get_bridge()
        try:
            if deep:
                entries = list((await bridge.find(location, withdirs=True)).values())
            else:
                entries = await bridge.ls(location, detail=True)
        except FileNotFoundError:
            return
        for entry in entries:
            attributes = self._map_entry(entry, requested)
            if attributes is not None:
                yield attributes

    def _map_entry(self, entry: Mapping[str, object], requested: str) -> StorageAttributes | None:
        """Turn one raw listing entry into an attributes record, or drop it.

        Dropped when it is the listed directory itself, or a marker a subclass
        hides. The path is brought back into the caller's terms — the root
        stripped off — and a directory and a file answer different questions, so
        each gets its own record.
        """
        relative = self._prefixer.strip_prefix(str(entry.get("name", "")))
        normalized = relative.strip("/")
        if normalized in ("", requested) or self._is_hidden_entry(relative):
            return None
        if entry.get("type") == "directory":
            return DirectoryAttributes(path=normalized, last_modified=self._epoch(entry))
        size = entry.get("size")
        return FileAttributes(
            path=normalized,
            file_size=size if isinstance(size, int) else None,
            last_modified=self._epoch(entry),
        )

    @override
    async def move(self, source: str, destination: str, config: Config) -> None:
        """Move ``source`` onto ``destination``, then settle its visibility."""
        if source == destination:
            return
        retained = await self._retained_visibility(source, config)
        try:
            await self._get_bridge().mv(
                self._prefixer.prefix_path(source),
                self._prefixer.prefix_path(destination),
            )
        except FileNotFoundError as error:
            raise UnableToMoveFileError(
                source, destination, "the source file does not exist"
            ) from error
        except OSError as error:
            raise UnableToMoveFileError(source, destination) from error
        await self._apply_transfer_visibility(destination, config, retained)

    @override
    async def copy(self, source: str, destination: str, config: Config) -> None:
        """Copy ``source`` onto ``destination``, then settle its visibility."""
        if source == destination:
            return
        retained = await self._retained_visibility(source, config)
        try:
            await self._get_bridge().cp_file(
                self._prefixer.prefix_path(source),
                self._prefixer.prefix_path(destination),
            )
        except FileNotFoundError as error:
            raise UnableToCopyFileError(
                source, destination, "the source file does not exist"
            ) from error
        except OSError as error:
            raise UnableToCopyFileError(source, destination) from error
        await self._apply_transfer_visibility(destination, config, retained)

    async def _retained_visibility(self, source: str, config: Config) -> Visibility | None:
        """Read the source's visibility before a transfer, when one is to be kept.

        Nothing when a call names a visibility of its own — that wins, applied
        after — or when the caller asked not to retain, or when the backend has
        no visibility to read. Read before the move so a source that vanishes has
        already given its answer.
        """
        if config.visibility_option(Config.VISIBILITY) is not None:
            return None
        if not config.bool_option(Config.RETAIN_VISIBILITY, default=True):
            return None
        try:
            return (await self.visibility(source)).visibility
        except (FeatureNotSupportedError, UnableToRetrieveMetadataError):
            return None

    async def _apply_transfer_visibility(
        self,
        destination: str,
        config: Config,
        retained: Visibility | None,
    ) -> None:
        """Set the destination's visibility after a transfer, per the rule.

        A visibility named in the call is applied and may raise
        :class:`FeatureNotSupportedError` — the caller asked for something the
        backend cannot do. A retained one is applied quietly, a backend without
        visibility simply keeping none.
        """
        explicit = config.visibility_option(Config.VISIBILITY)
        if explicit is not None:
            await self.set_visibility(destination, explicit)
        elif retained is not None:
            try:
                await self.set_visibility(destination, retained)
            except FeatureNotSupportedError:
                return

    @override
    async def file_size(self, path: str) -> FileAttributes:
        """Return the size of the file at ``path``."""
        info = await self._info(path, "file_size")
        if info.get("type") == "directory":
            raise UnableToRetrieveMetadataError.file_size(path, "the path is a directory")
        size = info.get("size")
        if not isinstance(size, int):
            raise UnableToRetrieveMetadataError.file_size(path)
        return FileAttributes(path=path, file_size=size)

    @override
    async def last_modified(self, path: str) -> FileAttributes:
        """Return when the file at ``path`` last changed, in whole epoch seconds."""
        info = await self._info(path, "last_modified")
        epoch = self._epoch(info)
        if epoch is None:
            raise UnableToRetrieveMetadataError.last_modified(path)
        return FileAttributes(path=path, last_modified=epoch)

    @override
    async def mime_type(self, path: str) -> FileAttributes:
        """Return what the file at ``path`` holds, from the backend or the name."""
        info = await self._info(path, "mime_type")
        if info.get("type") == "directory":
            raise UnableToRetrieveMetadataError.mime_type(path, "the path is a directory")
        resolved = self._content_type(info) or self._mime_detector.detect_from_path(path)
        if resolved is None:
            raise UnableToRetrieveMetadataError.mime_type(path)
        return FileAttributes(path=path, mime_type=resolved)

    @override
    async def visibility(self, path: str) -> FileAttributes:
        """Raise: a plain filesystem adapter has no notion of visibility."""
        del path
        raise FeatureNotSupportedError(Feature.VISIBILITY, type(self).__name__)

    @override
    async def set_visibility(self, path: str, visibility: Visibility) -> None:
        """Raise: a plain filesystem adapter has no notion of visibility."""
        del path, visibility
        raise FeatureNotSupportedError(Feature.VISIBILITY, type(self).__name__)

    @override
    async def close(self) -> None:
        """Close the backend's session, if one was opened; safe to call again."""
        if self._bridge is not None:
            await self._bridge.close()

    async def _info(self, path: str, metadata_type: str) -> Mapping[str, object]:
        """Read a file's raw facts, turning a miss into a metadata failure."""
        location = self._prefixer.prefix_path(path)
        try:
            return await self._get_bridge().info(location)
        except FileNotFoundError as error:
            raise UnableToRetrieveMetadataError(
                path, metadata_type, "the file does not exist"
            ) from error
        except OSError as error:
            raise UnableToRetrieveMetadataError(path, metadata_type) from error

    @staticmethod
    def _content_type(info: Mapping[str, object]) -> str | None:
        """Return the media type a backend kept for a file, if it kept one."""
        for key in _CONTENT_TYPE_KEYS:
            value = info.get(key)
            if isinstance(value, str) and value != "":
                return value
        return None

    @staticmethod
    def _epoch(info: Mapping[str, object]) -> int | None:
        """Return a file's last-write time as whole epoch seconds, however kept.

        Backends time a file differently and in different shapes — a float, an
        integer, a moment, an ISO string — so each candidate key is tried in
        turn and the first that yields a number wins.
        """
        for key in _LAST_MODIFIED_KEYS:
            if key not in info:
                continue
            epoch = _to_epoch_seconds(info[key])
            if epoch is not None:
                return epoch
        return None


def _to_epoch_seconds(value: object) -> int | None:
    """Turn a timestamp of any of the shapes a backend uses into epoch seconds."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, datetime):
        return int(value.timestamp())
    if isinstance(value, str):
        try:
            return int(datetime.fromisoformat(value).timestamp())
        except ValueError:
            return None
    return None
