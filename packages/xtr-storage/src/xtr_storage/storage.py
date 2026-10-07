"""The front door to one backend: paths in, reads, writes, listings and urls out."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterable, Iterable, Sequence
from io import IOBase, TextIOBase
from typing import TYPE_CHECKING, Final, cast, final

from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.directory_listing import DirectoryListing
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    FeatureNotSupportedError,
    InvalidArgumentError,
    InvalidStreamError,
    UnableToCopyFileError,
    UnableToGeneratePublicUrlError,
    UnableToGenerateTemporaryUrlError,
    UnableToListContentsError,
    UnableToMoveFileError,
    UnableToRetrieveMetadataError,
)
from xtr_storage.identical_path_policy import IdenticalPathPolicy
from xtr_storage.path.whitespace_path_normalizer import WhitespacePathNormalizer
from xtr_storage.url_generation.prefix_public_url_generator import PrefixPublicUrlGenerator
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface
from xtr_storage.url_generation.sharded_prefix_public_url_generator import (
    ShardedPrefixPublicUrlGenerator,
)
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping
    from datetime import datetime
    from types import TracebackType
    from typing import BinaryIO

    from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
    from xtr_storage.path.path_normalizer_interface import PathNormalizerInterface
    from xtr_storage.storage_attributes import StorageAttributes

__all__ = ["Storage"]

CHUNK_SIZE: Final = 1_048_576
"""How much of a binary file is read at a time, so a large upload never lands in memory whole."""

_DEFAULT_CHECKSUM_ALGORITHM: Final = "md5"


@final
class Storage:
    """One backend behind the whole reading-and-writing contract.

    A storage is what an application holds and passes around: it turns a
    caller's path into a backend operation, and it is the single place a path
    is cleaned, options are layered, a stream is made uniform and a capability
    a backend lacks is either worked around or refused. The adapter it wraps
    receives the result of all that and never has to second-guess a caller.

    The options a storage is built with are the standing defaults; the mapping
    a single call passes is laid over them for that call alone, so one upload
    can be public without changing what the next one does.
    """

    __slots__ = (
        "_adapter",
        "_config",
        "_config_public_url_generator",
        "_path_normalizer",
        "_public_url_generator",
        "_temporary_url_generator",
    )

    _adapter: StorageAdapterInterface
    _config: Config
    _path_normalizer: PathNormalizerInterface
    _public_url_generator: PublicUrlGeneratorInterface | None
    _temporary_url_generator: TemporaryUrlGeneratorInterface | None
    _config_public_url_generator: tuple[object, PublicUrlGeneratorInterface] | None

    def __init__(
        self,
        adapter: StorageAdapterInterface,
        config: Mapping[str, object] | None = None,
        *,
        path_normalizer: PathNormalizerInterface | None = None,
        public_url_generator: PublicUrlGeneratorInterface | None = None,
        temporary_url_generator: TemporaryUrlGeneratorInterface | None = None,
    ) -> None:
        """Wrap ``adapter`` and fix the defaults every call starts from.

        Args:
            adapter: The backend to drive. It is handed normalized paths and a
                merged :class:`~xtr_storage.Config`, never a raw caller path.
            config: The standing options a call's own options are laid over.
            path_normalizer: How caller paths are reduced to the form the
                backend sees; a whitespace normalizer by default, reading
                whether ``..`` may climb from the config.
            public_url_generator: A generator put in front of the backend for
                lasting addresses; consulted before the backend's own.
            temporary_url_generator: The same, for expiring addresses.
        """
        self._adapter = adapter
        self._config = Config(config)
        if path_normalizer is None:
            allow_traversal = self._config.bool_option(
                Config.ALLOW_RELATIVE_PATH_TRAVERSAL,
                default=True,
            )
            path_normalizer = WhitespacePathNormalizer(allow_traversal)
        self._path_normalizer = path_normalizer
        self._public_url_generator = public_url_generator
        self._temporary_url_generator = temporary_url_generator
        self._config_public_url_generator = None

    def _normalize(self, path: str) -> str:
        """Reduce ``path`` to the single form a backend is ever shown."""
        return self._path_normalizer.normalize_path(path)

    def _merged(self, config: Mapping[str, object] | None) -> Config:
        """Lay a call's options over the standing ones, the newcomer winning."""
        return self._config.extend(config) if config is not None else self._config

    async def file_exists(self, location: str) -> bool:
        """Return whether a file is at ``location``."""
        return await self._adapter.file_exists(self._normalize(location))

    async def directory_exists(self, location: str) -> bool:
        """Return whether a directory is at ``location``."""
        return await self._adapter.directory_exists(self._normalize(location))

    async def has(self, location: str) -> bool:
        """Return whether anything at all is at ``location``, file or directory."""
        path = self._normalize(location)

        return await self._adapter.file_exists(path) or await self._adapter.directory_exists(path)

    async def read(self, location: str) -> bytes:
        """Return the whole contents of the file at ``location``.

        The whole file lands in memory, so reach for :meth:`read_stream` instead
        whenever the size is a caller's to decide — an upload, a remote object —
        rather than something this application wrote and knows the bound of.
        """
        return await self._adapter.read(self._normalize(location))

    def read_stream(self, location: str) -> AsyncIterator[bytes]:
        """Return the file's contents in chunks, reaching the backend as they are taken."""
        return self._adapter.read_stream(self._normalize(location))

    def list_contents(
        self,
        location: str = "",
        deep: bool = False,
    ) -> DirectoryListing[StorageAttributes]:
        """Return a lazy listing of what is under ``location``.

        Nothing is read here: the returned listing reaches the backend only
        once it is iterated, and any failure that surfaces then — whatever the
        backend raised — arrives as an :class:`UnableToListContentsError`
        carrying it as ``__cause__``. A :class:`FeatureNotSupportedError`
        passes through unwrapped, so a caller that can list without descending
        can tell "this backend cannot" apart from "this listing failed".
        """
        path = self._normalize(location)

        def source() -> AsyncIterator[StorageAttributes]:
            return self._wrap_listing(location, path, deep)

        return DirectoryListing(source)

    async def _wrap_listing(
        self,
        location: str,
        path: str,
        deep: bool,
    ) -> AsyncIterator[StorageAttributes]:
        """Iterate the adapter's listing, turning any failure into the listing error."""
        try:
            async for entry in self._adapter.list_contents(path, deep):
                yield entry
        except (UnableToListContentsError, FeatureNotSupportedError):
            raise
        except Exception as error:
            raise UnableToListContentsError(location, deep=deep) from error

    async def last_modified(self, path: str) -> int:
        """Return when the file at ``path`` last changed, in whole epoch seconds."""
        attributes = await self._adapter.last_modified(self._normalize(path))
        if attributes.last_modified is None:
            raise UnableToRetrieveMetadataError.last_modified(path)

        return attributes.last_modified

    async def file_size(self, path: str) -> int:
        """Return the size in bytes of the file at ``path``."""
        attributes = await self._adapter.file_size(self._normalize(path))
        if attributes.file_size is None:
            raise UnableToRetrieveMetadataError.file_size(path)

        return attributes.file_size

    async def mime_type(self, path: str) -> str:
        """Return what the file at ``path`` holds."""
        attributes = await self._adapter.mime_type(self._normalize(path))
        if attributes.mime_type is None:
            raise UnableToRetrieveMetadataError.mime_type(path)

        return attributes.mime_type

    async def visibility(self, path: str) -> Visibility:
        """Return who may read the file at ``path``."""
        attributes = await self._adapter.visibility(self._normalize(path))
        if attributes.visibility is None:
            raise UnableToRetrieveMetadataError.visibility(path)

        return attributes.visibility

    async def write(
        self,
        location: str,
        contents: bytes,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Write ``contents`` at ``location``, replacing whatever was there."""
        await self._adapter.write(self._normalize(location), contents, self._merged(config))

    async def write_stream(
        self,
        location: str,
        contents: AsyncIterable[bytes] | Iterable[bytes] | BinaryIO,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Write at ``location`` from a source read in pieces.

        An async source is used as it is; a plain iterable is wrapped in one;
        an open binary file is rewound when it can be and read a megabyte at a
        time off the event loop. Text is refused, because encoding it is the
        caller's decision, not a guess this makes.
        """
        stream = _coerce_stream(contents)
        await self._adapter.write_stream(self._normalize(location), stream, self._merged(config))

    async def set_visibility(self, path: str, visibility: Visibility | str) -> None:
        """Change who may read the file or directory at ``path``."""
        await self._adapter.set_visibility(self._normalize(path), Visibility.parse(visibility))

    async def delete(self, location: str) -> None:
        """Delete the file at ``location``, treating a missing one as already gone."""
        await self._adapter.delete(self._normalize(location))

    async def delete_directory(self, location: str) -> None:
        """Delete the directory at ``location`` and everything under it."""
        await self._adapter.delete_directory(self._normalize(location))

    async def create_directory(
        self,
        location: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Create the directory at ``location``, and the ones leading to it."""
        await self._adapter.create_directory(self._normalize(location), self._merged(config))

    async def move(
        self,
        source: str,
        destination: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Move the file at ``source`` to ``destination``, overwriting it.

        Raises:
            UnableToMoveFileError: Under the ``fail`` policy when the two paths
                are the same, and under the ``ignore`` policy when they are the
                same and no file is there: nothing was moved, so answering
                success would tell the caller a file exists that does not.
        """
        from_path = self._normalize(source)
        to_path = self._normalize(destination)
        merged = self._merged(config)
        if from_path == to_path:
            policy = merged.identical_path_policy(Config.MOVE_IDENTICAL_PATH)
            if policy is IdenticalPathPolicy.FAIL:
                raise UnableToMoveFileError(source, destination, _SAME_PATH)
            if policy is IdenticalPathPolicy.IGNORE:
                if not await self._adapter.file_exists(from_path):
                    raise UnableToMoveFileError(source, destination, _MISSING_SOURCE)
                return

        await self._adapter.move(from_path, to_path, self._transfer_config(config))

    async def copy(
        self,
        source: str,
        destination: str,
        config: Mapping[str, object] | None = None,
    ) -> None:
        """Copy the file at ``source`` to ``destination``, overwriting it.

        Raises:
            UnableToCopyFileError: Under the ``fail`` policy when the two paths
                are the same, and under the ``ignore`` policy when they are the
                same and no file is there: nothing was copied, so answering
                success would tell the caller a file exists that does not.
        """
        from_path = self._normalize(source)
        to_path = self._normalize(destination)
        merged = self._merged(config)
        if from_path == to_path:
            policy = merged.identical_path_policy(Config.COPY_IDENTICAL_PATH)
            if policy is IdenticalPathPolicy.FAIL:
                raise UnableToCopyFileError(source, destination, _SAME_PATH)
            if policy is IdenticalPathPolicy.IGNORE:
                if not await self._adapter.file_exists(from_path):
                    raise UnableToCopyFileError(source, destination, _MISSING_SOURCE)
                return

        await self._adapter.copy(from_path, to_path, self._transfer_config(config))

    def _transfer_config(self, config: Mapping[str, object] | None) -> Config:
        """Build the config a copy or a move hands the adapter.

        A transfer keeps the source's visibility by default, so the storage's
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

    async def checksum(self, path: str, config: Mapping[str, object] | None = None) -> str:
        """Return a digest of the file at ``path``.

        A backend that keeps its own digest answers from it; otherwise, or when
        it keeps none of the algorithm asked for, the file's bytes are streamed
        through :mod:`hashlib` here.
        """
        normalized = self._normalize(path)
        merged = self._merged(config)
        if isinstance(self._adapter, ChecksumProviderInterface):
            try:
                return await self._adapter.checksum(normalized, merged)
            except ChecksumAlgorithmNotSupportedError:
                pass  # the backend keeps no such digest; compute it from the bytes

        algorithm = merged.str_option(Config.CHECKSUM_ALGORITHM, _DEFAULT_CHECKSUM_ALGORITHM)
        return await self._stream_checksum(normalized, algorithm)

    async def _stream_checksum(self, path: str, algorithm: str) -> str:
        """Read the file at ``path`` and digest it with ``algorithm``."""
        if algorithm not in hashlib.algorithms_available:
            raise InvalidArgumentError(f"the checksum algorithm {algorithm!r} is unknown")

        digest = hashlib.new(algorithm)
        async for chunk in self._adapter.read_stream(path):
            digest.update(chunk)

        return digest.hexdigest()

    async def public_url(self, path: str, config: Mapping[str, object] | None = None) -> str:
        """Return a lasting address the file at ``path`` is reachable at.

        An injected generator is asked first, then one built from the
        ``public_url`` option, and only then the backend's own — a caller that
        supplied nothing and a backend that knows nothing leave a storage with
        no address to give.
        """
        normalized = self._normalize(path)
        merged = self._merged(config)
        if self._public_url_generator is not None:
            return await self._public_url_generator.public_url(normalized, merged)

        from_config = self._config_url_generator(merged)
        if from_config is not None:
            return await from_config.public_url(normalized, merged)

        if isinstance(self._adapter, PublicUrlGeneratorInterface):
            return await self._adapter.public_url(normalized, merged)

        raise UnableToGeneratePublicUrlError(path, "no public url generator is configured")

    def _config_url_generator(self, config: Config) -> PublicUrlGeneratorInterface | None:
        """Build (and remember) the generator the ``public_url`` option describes."""
        setting = config.get(Config.PUBLIC_URL)
        if setting is None:
            return None

        remembered = self._config_public_url_generator
        if remembered is not None and remembered[0] == setting:
            return remembered[1]

        generator = _build_url_generator(setting)
        self._config_public_url_generator = (setting, generator)

        return generator

    async def temporary_url(
        self,
        path: str,
        expires_at: datetime,
        config: Mapping[str, object] | None = None,
    ) -> str:
        """Return an address for the file at ``path`` that stops working at ``expires_at``.

        The deadline has to name one instant everywhere, so a moment carrying
        no timezone is refused before any generator is asked.
        """
        if expires_at.tzinfo is None or expires_at.utcoffset() is None:
            raise InvalidArgumentError("expires_at must carry a timezone")

        normalized = self._normalize(path)
        merged = self._merged(config)
        if self._temporary_url_generator is not None:
            return await self._temporary_url_generator.temporary_url(normalized, expires_at, merged)

        if isinstance(self._adapter, TemporaryUrlGeneratorInterface):
            return await self._adapter.temporary_url(normalized, expires_at, merged)

        raise UnableToGenerateTemporaryUrlError(path, "no temporary url generator is configured")

    async def close(self) -> None:
        """Release whatever the adapter holds open; it stays usable afterwards."""
        await self._adapter.close()

    async def __aenter__(self) -> Storage:
        """Enter a context that closes the storage on the way out."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the storage, whatever the block did."""
        del exc_type, exc, traceback
        await self.close()


_SAME_PATH: Final = "source and destination are the same"

_MISSING_SOURCE: Final = "the source file does not exist"


async def _binary_io_stream(stream: BinaryIO) -> AsyncIterator[bytes]:
    """Read an open binary file a megabyte at a time, rewinding it first when it can be."""
    if stream.seekable() and stream.tell() != 0:
        _ = await asyncio.to_thread(stream.seek, 0)

    while True:
        chunk = await asyncio.to_thread(stream.read, CHUNK_SIZE)
        if not chunk:
            break

        yield chunk


async def _iterable_stream(chunks: Iterable[bytes]) -> AsyncIterator[bytes]:
    """Present a plain iterable of chunks as the async source an adapter expects."""
    for chunk in chunks:
        yield chunk


def _coerce_stream(contents: object) -> AsyncIterable[bytes]:
    """Turn whatever a caller handed in into the one shape an adapter writes from.

    Text is not a stream: encoding it is a decision, and guessing the encoding
    is how files become unreadable. So :class:`str` and raw :class:`bytes` are
    refused rather than iterated — and so is a text file object, whose
    :class:`~io.TextIOBase` is an :class:`~io.IOBase` and would otherwise be read
    as if it yielded bytes.
    """
    if isinstance(contents, (str, bytes, bytearray)):
        raise InvalidStreamError(type(contents).__name__)
    if isinstance(contents, TextIOBase):
        raise InvalidStreamError(type(contents).__name__)
    if isinstance(contents, IOBase):
        return _binary_io_stream(cast("BinaryIO", cast("object", contents)))
    if isinstance(contents, AsyncIterable):
        return cast("AsyncIterable[bytes]", contents)
    if isinstance(contents, Iterable):
        return _iterable_stream(cast("Iterable[bytes]", contents))

    raise InvalidStreamError(type(contents).__name__)


def _build_url_generator(setting: object) -> PublicUrlGeneratorInterface:
    """Read the ``public_url`` option: one url is a prefix, several are shards."""
    if isinstance(setting, str):
        return PrefixPublicUrlGenerator(setting)
    if isinstance(setting, Sequence):
        prefixes = [item for item in setting if isinstance(item, str)]
        if len(prefixes) == len(setting) and len(prefixes) > 0:
            return ShardedPrefixPublicUrlGenerator(prefixes)

    raise InvalidArgumentError(
        f'the "{Config.PUBLIC_URL}" option must be a url or a non-empty list of urls',
    )
