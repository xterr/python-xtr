from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.config import Config
from xtr_storage.directory_attributes import DirectoryAttributes
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, AsyncIterator

    from xtr_storage.storage_attributes import StorageAttributes


class FakeAdapter:
    """A dictionary of files, enough to exercise the shapes the storage relies on."""

    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.visibilities: dict[str, Visibility] = {}
        self.closed: int = 0

    async def file_exists(self, path: str) -> bool:
        return path in self.files

    async def directory_exists(self, path: str) -> bool:
        return any(name.startswith(f"{path}/") for name in self.files)

    async def write(self, path: str, contents: bytes, config: Config) -> None:
        del config

        self.files[path] = contents

    async def write_stream(self, path: str, contents: AsyncIterable[bytes], config: Config) -> None:
        del config

        self.files[path] = b"".join([chunk async for chunk in contents])

    async def read(self, path: str) -> bytes:
        return self.files[path]

    async def read_stream(self, path: str) -> AsyncIterator[bytes]:
        for chunk in (self.files[path][:1], self.files[path][1:]):
            yield chunk

    async def delete(self, path: str) -> None:
        _ = self.files.pop(path, None)

    async def delete_directory(self, path: str) -> None:
        for name in [name for name in self.files if name.startswith(f"{path}/")]:
            del self.files[name]

    async def create_directory(self, path: str, config: Config) -> None:
        del path, config

    async def set_visibility(self, path: str, visibility: Visibility) -> None:
        self.visibilities[path] = visibility

    async def visibility(self, path: str) -> FileAttributes:
        return FileAttributes(path, visibility=self.visibilities[path])

    async def mime_type(self, path: str) -> FileAttributes:
        return FileAttributes(path, mime_type="text/plain")

    async def last_modified(self, path: str) -> FileAttributes:
        return FileAttributes(path, last_modified=1_700_000_000)

    async def file_size(self, path: str) -> FileAttributes:
        return FileAttributes(path, file_size=len(self.files[path]))

    async def list_contents(self, path: str, deep: bool) -> AsyncIterator[StorageAttributes]:
        if deep:
            yield DirectoryAttributes(f"{path}/nested")

        for name in sorted(self.files):
            yield FileAttributes(name)

    async def move(self, source: str, destination: str, config: Config) -> None:
        del config

        self.files[destination] = self.files.pop(source)

    async def copy(self, source: str, destination: str, config: Config) -> None:
        del config

        self.files[destination] = self.files[source]

    async def close(self) -> None:
        self.closed += 1


def test_a_structural_match_satisfies_the_interface() -> None:
    assert isinstance(FakeAdapter(), StorageAdapterInterface)


def test_an_object_with_none_of_the_methods_does_not_satisfy_the_interface() -> None:
    class Empty:
        pass

    assert not isinstance(Empty(), StorageAdapterInterface)


def test_reading_alone_does_not_satisfy_the_interface() -> None:
    class OnlyReads:
        async def read(self, path: str) -> bytes:
            return path.encode()

    assert not isinstance(OnlyReads(), StorageAdapterInterface)


@pytest.mark.anyio
async def test_an_adapter_round_trips_bytes_through_the_interface() -> None:
    adapter: StorageAdapterInterface = FakeAdapter()

    await adapter.write("a.txt", b"contents", Config())

    assert await adapter.read("a.txt") == b"contents"
    assert (await adapter.file_size("a.txt")).file_size == 8


@pytest.mark.anyio
async def test_write_stream_takes_an_async_source() -> None:
    adapter: StorageAdapterInterface = FakeAdapter()

    async def chunks() -> AsyncIterator[bytes]:
        yield b"con"
        yield b"tents"

    await adapter.write_stream("a.txt", chunks(), Config())

    assert await adapter.read("a.txt") == b"contents"


@pytest.mark.anyio
async def test_read_stream_is_iterated_without_awaiting_the_call() -> None:
    adapter: StorageAdapterInterface = FakeAdapter()
    await adapter.write("a.txt", b"contents", Config())

    assert [chunk async for chunk in adapter.read_stream("a.txt")] == [b"c", b"ontents"]


@pytest.mark.anyio
async def test_list_contents_is_iterated_without_awaiting_the_call() -> None:
    adapter: StorageAdapterInterface = FakeAdapter()
    await adapter.write("photos/a.txt", b"contents", Config())

    entries = [entry.path async for entry in adapter.list_contents("photos", deep=True)]

    assert entries == ["photos/nested", "photos/a.txt"]


@pytest.mark.anyio
async def test_metadata_comes_back_as_an_attributes_record() -> None:
    adapter: StorageAdapterInterface = FakeAdapter()
    await adapter.write("a.txt", b"contents", Config())

    await adapter.set_visibility("a.txt", Visibility.PRIVATE)

    assert await adapter.visibility("a.txt") == FileAttributes(
        "a.txt", visibility=Visibility.PRIVATE
    )


@pytest.mark.anyio
async def test_closing_twice_is_not_an_error() -> None:
    fake = FakeAdapter()
    adapter: StorageAdapterInterface = fake

    await adapter.close()
    await adapter.close()

    assert fake.closed == 2
