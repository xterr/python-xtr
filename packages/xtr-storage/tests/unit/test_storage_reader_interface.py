from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_storage.directory_attributes import DirectoryAttributes
from xtr_storage.directory_listing import DirectoryListing
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.storage_reader_interface import StorageReaderInterface
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_storage.storage_attributes import StorageAttributes


class FakeReader:
    """One file, answered for every question, so the shapes can be exercised."""

    async def file_exists(self, location: str) -> bool:
        return location == "a.txt"

    async def directory_exists(self, location: str) -> bool:
        return location == "photos"

    async def has(self, location: str) -> bool:
        return location in {"a.txt", "photos"}

    async def read(self, location: str) -> bytes:
        return location.encode()

    async def read_stream(self, location: str) -> AsyncIterator[bytes]:
        for chunk in (location.encode(), b"!"):
            yield chunk

    def list_contents(
        self, location: str = "", deep: bool = False
    ) -> DirectoryListing[StorageAttributes]:
        async def entries() -> AsyncIterator[StorageAttributes]:
            yield FileAttributes(f"{location}a.txt" if location else "a.txt")

            if deep:
                yield DirectoryAttributes("photos")

        return DirectoryListing(entries)

    async def last_modified(self, path: str) -> int:
        del path

        return 1_700_000_000

    async def file_size(self, path: str) -> int:
        return len(path)

    async def mime_type(self, path: str) -> str:
        del path

        return "text/plain"

    async def visibility(self, path: str) -> Visibility:
        del path

        return Visibility.PRIVATE


def test_a_structural_match_satisfies_the_interface() -> None:
    assert isinstance(FakeReader(), StorageReaderInterface)


def test_an_object_with_none_of_the_methods_does_not_satisfy_the_interface() -> None:
    class Empty:
        pass

    assert not isinstance(Empty(), StorageReaderInterface)


def test_reading_alone_does_not_satisfy_the_interface() -> None:
    class OnlyReads:
        async def read(self, location: str) -> bytes:
            return location.encode()

    assert not isinstance(OnlyReads(), StorageReaderInterface)


@pytest.mark.anyio
async def test_a_reader_answers_through_the_interface() -> None:
    reader: StorageReaderInterface = FakeReader()

    assert await reader.read("a.txt") == b"a.txt"
    assert await reader.file_exists("a.txt")
    assert await reader.visibility("a.txt") is Visibility.PRIVATE


@pytest.mark.anyio
async def test_read_stream_is_taken_chunk_by_chunk_without_awaiting_the_call() -> None:
    reader: StorageReaderInterface = FakeReader()

    chunks = [chunk async for chunk in reader.read_stream("a.txt")]

    assert chunks == [b"a.txt", b"!"]


@pytest.mark.anyio
async def test_list_contents_hands_back_a_listing_without_being_awaited() -> None:
    reader: StorageReaderInterface = FakeReader()

    listing = reader.list_contents("photos/", deep=True)

    assert [entry.path async for entry in listing] == ["photos/a.txt", "photos"]
