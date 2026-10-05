from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_storage.directory_attributes import DirectoryAttributes
from xtr_storage.directory_listing import DirectoryListing
from xtr_storage.exception import UnableToListContentsError
from xtr_storage.file_attributes import FileAttributes

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from xtr_storage.storage_attributes import StorageAttributes


class CountingSource:
    """A source factory that records how often it was asked to start reading."""

    def __init__(self, *entries: StorageAttributes) -> None:
        self.entries: Sequence[StorageAttributes] = entries
        self.starts: int = 0
        self.yielded: int = 0

    def __call__(self) -> AsyncIterator[StorageAttributes]:
        self.starts += 1

        return self._read()

    async def _read(self) -> AsyncIterator[StorageAttributes]:
        for entry in self.entries:
            self.yielded += 1

            yield entry


@pytest.mark.anyio
async def test_it_yields_what_the_source_yields() -> None:
    source = CountingSource(FileAttributes("a.txt"), FileAttributes("b.txt"))

    assert [entry.path async for entry in DirectoryListing(source)] == ["a.txt", "b.txt"]


@pytest.mark.anyio
async def test_to_list_returns_every_entry() -> None:
    source = CountingSource(FileAttributes("a.txt"), DirectoryAttributes("photos"))

    assert await DirectoryListing(source).to_list() == [
        FileAttributes("a.txt"),
        DirectoryAttributes("photos"),
    ]


def test_building_a_listing_reads_nothing() -> None:
    source = CountingSource(FileAttributes("a.txt"))

    _ = DirectoryListing(source)

    assert source.starts == 0


def test_filter_reads_nothing_until_something_iterates() -> None:
    source = CountingSource(FileAttributes("a.txt"), FileAttributes("b.log"))

    _ = DirectoryListing(source).filter(lambda entry: entry.path.endswith(".txt"))

    assert (source.starts, source.yielded) == (0, 0)


def test_map_reads_nothing_until_something_iterates() -> None:
    source = CountingSource(FileAttributes("a.txt"))

    _ = DirectoryListing(source).map(lambda entry: entry.path)

    assert (source.starts, source.yielded) == (0, 0)


def test_sort_by_path_reads_nothing_until_something_iterates() -> None:
    source = CountingSource(FileAttributes("b.txt"), FileAttributes("a.txt"))

    _ = DirectoryListing(source).sort_by_path()

    assert (source.starts, source.yielded) == (0, 0)


@pytest.mark.anyio
async def test_it_keeps_only_the_entries_the_predicate_accepts() -> None:
    source = CountingSource(
        FileAttributes("keep.txt"),
        FileAttributes("drop.log"),
        FileAttributes("also-keep.txt"),
    )

    kept = DirectoryListing(source).filter(lambda entry: entry.path.endswith(".txt"))

    assert [entry.path async for entry in kept] == ["keep.txt", "also-keep.txt"]


@pytest.mark.anyio
async def test_it_yields_each_entry_as_the_transform_describes_it() -> None:
    source = CountingSource(FileAttributes("a.txt"), DirectoryAttributes("photos"))

    described = DirectoryListing(source).map(lambda entry: entry.type)

    assert await described.to_list() == ["file", "dir"]


@pytest.mark.anyio
async def test_sort_by_path_orders_files_and_directories_together() -> None:
    source = CountingSource(
        FileAttributes("b/z.txt"),
        DirectoryAttributes("a"),
        FileAttributes("b/a.txt"),
    )

    ordered = DirectoryListing(source).sort_by_path()

    assert [entry.path async for entry in ordered] == ["a", "b/a.txt", "b/z.txt"]


@pytest.mark.anyio
async def test_an_error_from_the_source_surfaces_only_when_iterating() -> None:
    async def failing() -> AsyncIterator[StorageAttributes]:
        yield FileAttributes("a.txt")

        raise UnableToListContentsError("photos", deep=False)

    narrowed = DirectoryListing(failing).filter(lambda entry: entry.is_file).sort_by_path()

    with pytest.raises(UnableToListContentsError):
        _ = await narrowed.to_list()


@pytest.mark.anyio
async def test_iterating_twice_asks_the_source_for_a_fresh_read() -> None:
    source = CountingSource(FileAttributes("a.txt"))
    listing = DirectoryListing(source)

    first = await listing.to_list()
    second = await listing.to_list()

    assert (first, second, source.starts) == ([FileAttributes("a.txt")], first, 2)


@pytest.mark.anyio
async def test_a_chain_of_steps_reads_the_source_once() -> None:
    source = CountingSource(
        FileAttributes("b.txt"),
        DirectoryAttributes("photos"),
        FileAttributes("a.txt"),
    )

    paths = (
        DirectoryListing(source)
        .filter(lambda entry: entry.is_file)
        .sort_by_path()
        .map(lambda entry: entry.path)
    )

    assert await paths.to_list() == ["a.txt", "b.txt"]
    assert (source.starts, source.yielded) == (1, 3)
