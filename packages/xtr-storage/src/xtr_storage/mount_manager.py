"""Several storages under one, each reached by the name it was mounted at."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Protocol, final, runtime_checkable

from xtr_storage.config import Config
from xtr_storage.exception import (
    FeatureNotSupportedError,
    StorageOperationFailedError,
    UnableToCopyFileError,
    UnableToMoveFileError,
    UnableToResolveMountError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Iterable, Mapping
    from datetime import datetime
    from types import TracebackType
    from typing import BinaryIO

    from xtr_storage.directory_listing import DirectoryListing
    from xtr_storage.storage_attributes import StorageAttributes
    from xtr_storage.storage_operator_interface import StorageOperatorInterface
    from xtr_storage.visibility import Visibility

__all__ = ["MountManager"]

_SEPARATOR: Final = "://"
"""What tells the name a storage is mounted under from the path inside it."""


@runtime_checkable
class _Closeable(Protocol):
    """A storage that holds something open and knows how to let go of it.

    Closing is not part of what a storage *is* — a mounted one may be a plain
    reader-writer with nothing to release — so it is asked for rather than
    assumed, and a storage that cannot be closed is simply left alone.
    """

    async def close(self) -> None:
        """Release whatever the storage holds open."""
        ...


@final
@dataclass(frozen=True, slots=True)
class _Route:
    """One location taken apart: which storage owns it, and where inside it."""

    storage: StorageOperatorInterface
    name: str
    path: str

    @property
    def location(self) -> str:
        """The location as the caller wrote it, for an error to quote back."""
        return f"{self.name}{_SEPARATOR}{self.path}"


@final
class MountManager:
    """Several storages behind one, picked by the name a location starts with.

    An application that keeps uploads in one place, generated reports in
    another and a scratch area in a third ends up passing three storages
    around, and every function that touches a file has to be told which one it
    is for. A mount manager is the one object instead: the storages are named
    once, and from then on the name travels with the path —
    ``"uploads://avatars/1.png"`` — so a location is enough to act on.

    Every location reads ``<name>://<path>``. There is no default mount,
    because a location that quietly went somewhere would be exactly the bug
    this exists to remove, so one naming no mount, an empty mount or a mount
    nothing was put under is refused with
    :class:`~xtr_storage.exception.UnableToResolveMountError` before anything
    is attempted.

    Routing is all this does, bar one thing: a copy or a move between two
    different storages, which no backend can be asked to perform, and which
    :meth:`copy` and :meth:`move` describe.
    """

    __slots__ = ("_config", "_storages")

    _storages: dict[str, StorageOperatorInterface]
    _config: Config

    def __init__(
        self,
        storages: Mapping[str, StorageOperatorInterface],
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Mount ``storages`` under their names and fix the standing options.

        Args:
            storages: What each mount name stands for. Copied, so a later
                change to the caller's mapping cannot re-route live code.
            config: Options every call through this manager starts from. A
                call's own are laid over them, and the result reaches the
                owning storage as that call's options.
        """
        self._storages = dict(storages)
        self._config = Config(config)

    def _route(self, location: str) -> _Route:
        """Split ``location`` into the storage it names and the path inside it.

        Raises:
            UnableToResolveMountError: When the location carries no mount name,
                carries an empty one, or names one nothing is mounted under.
        """
        name, separator, path = location.partition(_SEPARATOR)
        if not separator:
            raise UnableToResolveMountError(
                location,
                f'a location must read "<mount>{_SEPARATOR}<path>"',
            )

        if not name:
            raise UnableToResolveMountError(location, "the mount name is empty")

        storage = self._storages.get(name)
        if storage is None:
            raise UnableToResolveMountError(location, f"nothing is mounted under {name!r}")

        return _Route(storage, name, path)

    def _options(self, config: Mapping[str, object] | None) -> dict[str, object]:
        """Lay a call's options over the standing ones, the newcomer winning."""
        return self._config.extend(config if config is not None else {}).to_dict()

    async def file_exists(self, location: str) -> bool:
        """Return whether a file is at ``location``."""
        route = self._route(location)

        return await route.storage.file_exists(route.path)

    async def directory_exists(self, location: str) -> bool:
        """Return whether a directory is at ``location``."""
        route = self._route(location)

        return await route.storage.directory_exists(route.path)

    async def has(self, location: str) -> bool:
        """Return whether anything at all is at ``location``, file or directory."""
        route = self._route(location)

        return await route.storage.has(route.path)

    async def read(self, location: str) -> bytes:
        """Return the whole contents of the file at ``location``."""
        route = self._route(location)

        return await route.storage.read(route.path)

    def read_stream(self, location: str) -> AsyncIterator[bytes]:
        """Return the file's contents in chunks, from the storage that holds it."""
        route = self._route(location)

        return route.storage.read_stream(route.path)

    def list_contents(
        self,
        location: str,
        deep: bool = False,
    ) -> DirectoryListing[StorageAttributes]:
        """Return a lazy listing of what is under ``location``.

        Every entry comes back at its full location — ``"uploads://a/b.png"``
        rather than ``"a/b.png"`` — so what a listing yields can be handed
        straight back to :meth:`read` or :meth:`copy` without the caller having
        to remember which mount it came from.

        The mount is resolved here rather than on first iteration: routing
        nowhere is a mistake in the call, and an error is worth more where the
        call is than wherever the listing is eventually read. There is no default
        location: a bare ``""`` names no mount, so the caller always says which
        storage to list.
        """
        route = self._route(location)
        prefix = f"{route.name}{_SEPARATOR}"

        def at_full_location(entry: StorageAttributes) -> StorageAttributes:
            return entry.with_path(f"{prefix}{entry.path}")

        return route.storage.list_contents(route.path, deep).map(at_full_location)

    async def last_modified(self, path: str) -> int:
        """Return when the file at ``path`` last changed, in whole epoch seconds."""
        route = self._route(path)

        return await route.storage.last_modified(route.path)

    async def file_size(self, path: str) -> int:
        """Return the size in bytes of the file at ``path``."""
        route = self._route(path)

        return await route.storage.file_size(route.path)

    async def mime_type(self, path: str) -> str:
        """Return what the file at ``path`` holds."""
        route = self._route(path)

        return await route.storage.mime_type(route.path)

    async def visibility(self, path: str) -> Visibility:
        """Return who may read the file at ``path``."""
        route = self._route(path)

        return await route.storage.visibility(route.path)

    async def write(
        self,
        location: str,
        contents: bytes,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Write ``contents`` at ``location``, replacing whatever was there."""
        route = self._route(location)
        await route.storage.write(route.path, contents, self._options(config))

    async def write_stream(
        self,
        location: str,
        contents: AsyncIterable[bytes] | Iterable[bytes] | BinaryIO,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Write at ``location`` from a source read in pieces."""
        route = self._route(location)
        await route.storage.write_stream(route.path, contents, self._options(config))

    async def set_visibility(self, path: str, visibility: Visibility | str) -> None:
        """Change who may read the file or directory at ``path``."""
        route = self._route(path)
        await route.storage.set_visibility(route.path, visibility)

    async def delete(self, location: str) -> None:
        """Delete the file at ``location``, treating a missing one as already gone."""
        route = self._route(location)
        await route.storage.delete(route.path)

    async def delete_directory(self, location: str) -> None:
        """Delete the directory at ``location`` and everything under it."""
        route = self._route(location)
        await route.storage.delete_directory(route.path)

    async def create_directory(
        self,
        location: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Create the directory at ``location``, and the ones leading to it."""
        route = self._route(location)
        await route.storage.create_directory(route.path, self._options(config))

    async def copy(
        self,
        source: str,
        destination: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Copy the file at ``source`` to ``destination``, overwriting it.

        Between two locations on the same storage this is that storage's own
        copy, which is where a backend does the work itself instead of sending
        every byte out and back. Between two storages it cannot be: the file is
        read out of one and written into the other a chunk at a time, and its
        visibility is read separately and named in the write, because nothing
        else carries it across. A visibility the call names wins over the
        source's, ``retain_visibility: False`` keeps none, a source that has no
        notion of visibility contributes none, and a destination that has none
        ignores what it is given.

        Raises:
            UnableToResolveMountError: When either location routes nowhere.
            UnableToCopyFileError: When the copy failed. Across two storages
                the read, the write and the visibility lookup all end here,
                carrying what actually failed as ``__cause__``.
        """
        from_route = self._route(source)
        to_route = self._route(destination)
        options = self._transfer_options(config)
        if from_route.storage is to_route.storage:
            await from_route.storage.copy(from_route.path, to_route.path, options.to_dict())

            return

        await self._copy_across(from_route, to_route, options)

    async def move(
        self,
        source: str,
        destination: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Move the file at ``source`` to ``destination``, overwriting it.

        Between two locations on the same storage this is that storage's own
        move. Between two storages it is a copy followed by a delete, which is
        the only thing it can be, and the delete is what makes it a move rather
        than a copy: when it fails the file is still at ``source``, and this
        says so instead of reporting a move that did not happen. Nothing is
        rolled back — the copy stands — so a caller that retries moves the same
        file again rather than losing it.

        Raises:
            UnableToResolveMountError: When either location routes nowhere.
            UnableToMoveFileError: When either half failed, carrying what
                actually failed as ``__cause__``.
        """
        from_route = self._route(source)
        to_route = self._route(destination)
        options = self._transfer_options(config)
        if from_route.storage is to_route.storage:
            await from_route.storage.move(from_route.path, to_route.path, options.to_dict())

            return

        try:
            await self._copy_across(from_route, to_route, options)
        except UnableToCopyFileError as error:
            raise UnableToMoveFileError(source, destination, error.reason) from error

        try:
            await from_route.storage.delete(from_route.path)
        except StorageOperationFailedError as error:
            raise UnableToMoveFileError(
                source,
                destination,
                f"the copy was made, but the source is still there: {error}",
            ) from error

    def _transfer_options(self, config: Mapping[str, object] | None) -> Config:
        """Build the options a copy or a move runs with.

        A transfer keeps the source's visibility by default, so this manager's
        own default visibility must not ride along and quietly override it. It
        is dropped unless the call itself named a visibility or turned keeping
        off.
        """
        call: Mapping[str, object] = config if config is not None else {}
        merged = self._config.extend(call)
        retain = merged.bool_option(Config.RETAIN_VISIBILITY, default=True)
        if retain and Config.VISIBILITY not in call:
            return self._config.without_settings(Config.VISIBILITY).extend(call)

        return merged

    async def _copy_across(
        self,
        source: _Route,
        destination: _Route,
        options: Config,
    ) -> None:
        """Stream a file from one storage into another, visibility and all.

        Whatever the read, the write or the visibility lookup raises arrives as
        one copy failure naming both full locations, so a caller handling a
        copy does not have to know it was the kind that crossed a backend.
        """
        try:
            visibility = options.visibility_option(Config.VISIBILITY)
            if visibility is None and options.bool_option(Config.RETAIN_VISIBILITY, default=True):
                visibility = await _visibility_of(source)

            if visibility is not None:
                options = options.with_setting(Config.VISIBILITY, visibility)

            await destination.storage.write_stream(
                destination.path,
                source.storage.read_stream(source.path),
                options.to_dict(),
            )
        except StorageOperationFailedError as error:
            raise UnableToCopyFileError(
                source.location, destination.location, str(error)
            ) from error

    async def public_url(self, path: str, config: Mapping[str, object] | None = None) -> str:
        """Return a lasting address for the file at ``path``, from its own storage."""
        route = self._route(path)

        return await route.storage.public_url(route.path, self._options(config))

    async def temporary_url(
        self,
        path: str,
        expires_at: datetime,
        config: Mapping[str, object] | None = None,
    ) -> str:
        """Return an expiring address for the file at ``path``, from its own storage."""
        route = self._route(path)

        return await route.storage.temporary_url(route.path, expires_at, self._options(config))

    async def checksum(self, path: str, config: Mapping[str, object] | None = None) -> str:
        """Return a digest of the file at ``path``, from the storage that holds it."""
        route = self._route(path)

        return await route.storage.checksum(route.path, self._options(config))

    async def close(self) -> None:
        """Close every mounted storage, whatever any one of them does about it.

        One storage refusing to close must not leave the rest open — a pool
        nobody shut is what outlives the process — so each is closed in turn,
        and every failure is raised together, in an :class:`ExceptionGroup`, once
        they all have been, so none is lost behind another. A storage with
        nothing to close is passed over.
        """
        failures: list[Exception] = []
        for storage in self._storages.values():
            failure = await _close_quietly(storage)
            if failure is not None:
                failures.append(failure)

        if failures:
            raise ExceptionGroup("one or more mounted storages failed to close", failures)

    async def __aenter__(self) -> MountManager:
        """Enter a context that closes every mounted storage on the way out."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close every mounted storage, whatever the block did."""
        del exc_type, exc, traceback
        await self.close()


async def _visibility_of(route: _Route) -> Visibility | None:
    """Return who may read the source file, or nothing where that is no question.

    A backend with no notion of visibility is not a copy that failed: it has
    nothing to carry over, and the destination keeps whatever it would give a
    file written straight into it.
    """
    try:
        return await route.storage.visibility(route.path)
    except FeatureNotSupportedError:
        return None


async def _close_quietly(storage: StorageOperatorInterface) -> Exception | None:
    """Close one storage and hand back what it raised, rather than raising it.

    So that a failure is kept until every other storage has had its turn.
    """
    if not isinstance(storage, _Closeable):
        return None

    try:
        await storage.close()
    except Exception as error:  # noqa: BLE001 -- a storage may close over any backend, and whatever it raises is handed back to be raised after the rest have closed
        return error

    return None
