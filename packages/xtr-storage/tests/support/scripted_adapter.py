"""A dictionary-backed adapter that a facade test can drive and interrogate.

The adapter under a :class:`~xtr_storage.Storage` is where behaviour actually
happens, so a facade test needs one whose every answer it controls. This fake
keeps files and their visibility in dictionaries, records the path and config
each call arrived with, and lets a test arm any method to raise. It is not a
backend — it never touches disk — but it satisfies the same
:class:`~xtr_storage.adapter.StorageAdapterInterface`, which the contract test
beside it proves.

Capabilities are opt-in by subclass rather than flag, because a storage decides
what an adapter can do with :func:`isinstance` against the capability protocols:
a base adapter must not answer to ``checksum`` merely because a flag is off, or
the storage would call it and never fall back.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_storage.config import Config
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    UnableToReadFileError,
)
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator, Mapping
    from datetime import datetime

    from xtr_storage.storage_attributes import StorageAttributes

__all__ = [
    "ChecksumScriptedAdapter",
    "PublicUrlScriptedAdapter",
    "ScriptedAdapter",
    "TemporaryUrlScriptedAdapter",
]

_LAST_MODIFIED: int = 1_700_000_000
_MIME_TYPE: str = "text/plain"


class ScriptedAdapter:
    """A backend a test scripts: it holds the files, and remembers every call.

    Args:
        files: The files the adapter starts with, path to bytes.
        visibility: The visibility each of those files starts with.
        fail_on: A method name to the exception raised the next time it runs;
            how a test drives the facade's failure paths.
        default_visibility: What a file reports when none was set for it.
    """

    def __init__(
        self,
        *,
        files: Mapping[str, bytes] | None = None,
        visibility: Mapping[str, Visibility] | None = None,
        fail_on: Mapping[str, Exception] | None = None,
        default_visibility: Visibility = Visibility.PUBLIC,
    ) -> None:
        self.files: dict[str, bytes] = dict(files) if files is not None else {}
        self.visibilities: dict[str, Visibility] = (
            dict(visibility) if visibility is not None else {}
        )
        self.directories: set[str] = set()
        self.fail_on: dict[str, Exception] = dict(fail_on) if fail_on is not None else {}
        self.default_visibility: Visibility = default_visibility
        self.calls: list[str] = []
        self.received_paths: list[str] = []
        self.received_configs: list[Config] = []
        self.closed: bool = False

    def _record(self, method: str, path: str, config: Config | None = None) -> None:
        """Note a call so a test can assert what reached the backend, and how."""
        self.calls.append(f"{method} {path}")
        self.received_paths.append(path)
        if config is not None:
            self.received_configs.append(config)

    def _maybe_fail(self, method: str) -> None:
        """Raise the exception a test armed for ``method``, if it armed one."""
        error = self.fail_on.get(method)
        if error is not None:
            raise error

    async def file_exists(self, path: str) -> bool:
        self._record("file_exists", path)
        self._maybe_fail("file_exists")

        return path in self.files

    async def directory_exists(self, path: str) -> bool:
        self._record("directory_exists", path)
        self._maybe_fail("directory_exists")

        return path in self.directories or any(key.startswith(f"{path}/") for key in self.files)

    async def write(self, path: str, contents: bytes, config: Config) -> None:
        self._record("write", path, config)
        self._maybe_fail("write")
        self.files[path] = contents
        self._apply_visibility(path, config)

    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        self._record("write_stream", path, config)
        self._maybe_fail("write_stream")
        chunks = [chunk async for chunk in contents]
        self.files[path] = b"".join(chunks)
        self._apply_visibility(path, config)

    def _apply_visibility(self, path: str, config: Config) -> None:
        """Keep a written file's visibility when the config named one."""
        chosen = config.visibility_option(Config.VISIBILITY)
        if chosen is not None:
            self.visibilities[path] = chosen

    async def read(self, path: str) -> bytes:
        self._record("read", path)
        self._maybe_fail("read")
        if path not in self.files:
            raise UnableToReadFileError(path, "no such file")

        return self.files[path]

    async def read_stream(self, path: str) -> AsyncIterator[bytes]:
        self._record("read_stream", path)
        self._maybe_fail("read_stream")
        if path not in self.files:
            raise UnableToReadFileError(path, "no such file")

        yield self.files[path]

    async def delete(self, path: str) -> None:
        self._record("delete", path)
        self._maybe_fail("delete")
        _ = self.files.pop(path, None)
        _ = self.visibilities.pop(path, None)

    async def delete_directory(self, path: str) -> None:
        self._record("delete_directory", path)
        self._maybe_fail("delete_directory")
        prefix = f"{path}/"
        for key in [key for key in self.files if key.startswith(prefix)]:
            del self.files[key]
        self.directories.discard(path)

    async def create_directory(self, path: str, config: Config) -> None:
        self._record("create_directory", path, config)
        self._maybe_fail("create_directory")
        self.directories.add(path)

    async def set_visibility(self, path: str, visibility: Visibility) -> None:
        self._record("set_visibility", path)
        self._maybe_fail("set_visibility")
        self.visibilities[path] = visibility

    async def visibility(self, path: str) -> FileAttributes:
        self._record("visibility", path)
        self._maybe_fail("visibility")

        return FileAttributes(path, visibility=self.visibilities.get(path, self.default_visibility))

    async def mime_type(self, path: str) -> FileAttributes:
        self._record("mime_type", path)
        self._maybe_fail("mime_type")

        return FileAttributes(path, mime_type=_MIME_TYPE)

    async def last_modified(self, path: str) -> FileAttributes:
        self._record("last_modified", path)
        self._maybe_fail("last_modified")

        return FileAttributes(path, last_modified=_LAST_MODIFIED)

    async def file_size(self, path: str) -> FileAttributes:
        self._record("file_size", path)
        self._maybe_fail("file_size")
        if path not in self.files:
            raise UnableToReadFileError(path, "no such file")

        return FileAttributes(path, file_size=len(self.files[path]))

    async def list_contents(self, path: str, deep: bool) -> AsyncIterator[StorageAttributes]:
        self._record("list_contents", path)
        self._maybe_fail("list_contents")
        del deep
        prefix = f"{path}/" if path else ""
        for key in sorted(self.files):
            if key.startswith(prefix):
                yield FileAttributes(key)

    async def move(self, source: str, destination: str, config: Config) -> None:
        self._record("move", f"{source}->{destination}", config)
        self._maybe_fail("move")
        self.files[destination] = self.files.pop(source)
        moved = self.visibilities.pop(source, None)
        if moved is not None:
            self.visibilities[destination] = moved

    async def copy(self, source: str, destination: str, config: Config) -> None:
        self._record("copy", f"{source}->{destination}", config)
        self._maybe_fail("copy")
        self.files[destination] = self.files[source]
        copied = self.visibilities.get(source)
        if copied is not None:
            self.visibilities[destination] = copied

    async def close(self) -> None:
        self.calls.append("close")
        self.closed = True


class ChecksumScriptedAdapter(ScriptedAdapter):
    """A scripted backend that keeps digests, for the checksum-provider path.

    Args:
        checksum_value: The digest it hands back for a supported algorithm.
        supported_algorithms: The algorithms it keeps; anything else makes it
            raise, which is the storage's cue to compute from the bytes.
    """

    def __init__(
        self,
        *,
        checksum_value: str = "backend-digest",
        supported_algorithms: tuple[str, ...] = ("etag",),
        files: Mapping[str, bytes] | None = None,
        fail_on: Mapping[str, Exception] | None = None,
    ) -> None:
        super().__init__(files=files, fail_on=fail_on)
        self.checksum_value: str = checksum_value
        self.supported_algorithms: frozenset[str] = frozenset(supported_algorithms)

    async def checksum(self, path: str, config: Config) -> str:
        self._record("checksum", path, config)
        self._maybe_fail("checksum")
        algorithm = config.str_option(Config.CHECKSUM_ALGORITHM, "md5")
        if algorithm not in self.supported_algorithms:
            raise ChecksumAlgorithmNotSupportedError(path, algorithm)

        return self.checksum_value


class PublicUrlScriptedAdapter(ScriptedAdapter):
    """A scripted backend whose objects each own a lasting address."""

    async def public_url(self, path: str, config: Config) -> str:
        self._record("public_url", path, config)
        self._maybe_fail("public_url")

        return f"https://backend.example/{path}"


class TemporaryUrlScriptedAdapter(ScriptedAdapter):
    """A scripted backend that can sign an address good until a deadline."""

    async def temporary_url(self, path: str, expires_at: datetime, config: Config) -> str:
        self._record("temporary_url", path, config)
        self._maybe_fail("temporary_url")

        return f"https://backend.example/{path}?expires={int(expires_at.timestamp())}"
