"""What the in-memory adapter owns beneath the shared contract.

The conformance suite proves it behaves like every other backend. These tests
pin the two things that are its own: that one adapter's files are nobody else's,
and that the visibility it keeps beside a file follows that file through a
write, a copy, a move and a deletion.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_storage.adapter.in_memory_adapter import InMemoryAdapter
from xtr_storage.config import Config
from xtr_storage.exception import UnableToRetrieveMetadataError, UnableToSetVisibilityError
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    """Yield the chunks in order, as the async source a streamed write takes."""
    for chunk in chunks:
        yield chunk


async def test_two_adapters_share_no_files() -> None:
    first = InMemoryAdapter()
    second = InMemoryAdapter()

    await first.write("mine.txt", b"mine", Config())

    assert await first.file_exists("mine.txt")
    assert not await second.file_exists("mine.txt")


async def test_constructing_the_adapter_opens_no_filesystem() -> None:
    adapter = InMemoryAdapter()

    assert adapter._bridge is None


async def test_a_write_takes_the_adapters_default_visibility() -> None:
    adapter = InMemoryAdapter(Visibility.PRIVATE)

    await adapter.write("a.txt", b"x", Config())

    assert (await adapter.visibility("a.txt")).visibility is Visibility.PRIVATE


async def test_a_write_takes_the_visibility_its_options_name() -> None:
    adapter = InMemoryAdapter()

    await adapter.write("a.txt", b"x", Config({Config.VISIBILITY: Visibility.PRIVATE.value}))

    assert (await adapter.visibility("a.txt")).visibility is Visibility.PRIVATE


async def test_a_streamed_write_records_a_visibility_too() -> None:
    adapter = InMemoryAdapter()

    await adapter.write_stream(
        "a.txt",
        _stream(b"x"),
        Config({Config.VISIBILITY: Visibility.PRIVATE.value}),
    )

    assert (await adapter.visibility("a.txt")).visibility is Visibility.PRIVATE


async def test_a_copy_keeps_the_sources_visibility() -> None:
    adapter = InMemoryAdapter()
    await adapter.write("a.txt", b"x", Config({Config.VISIBILITY: Visibility.PRIVATE.value}))

    await adapter.copy("a.txt", "b.txt", Config())

    assert (await adapter.visibility("b.txt")).visibility is Visibility.PRIVATE
    assert (await adapter.visibility("a.txt")).visibility is Visibility.PRIVATE


async def test_a_copy_takes_the_visibility_its_options_name_over_the_sources() -> None:
    adapter = InMemoryAdapter()
    await adapter.write("a.txt", b"x", Config({Config.VISIBILITY: Visibility.PRIVATE.value}))

    await adapter.copy("a.txt", "b.txt", Config({Config.VISIBILITY: Visibility.PUBLIC.value}))

    assert (await adapter.visibility("b.txt")).visibility is Visibility.PUBLIC


async def test_a_copy_asked_to_keep_nothing_carries_no_visibility() -> None:
    adapter = InMemoryAdapter()
    await adapter.write("a.txt", b"x", Config({Config.VISIBILITY: Visibility.PRIVATE.value}))

    await adapter.copy("a.txt", "b.txt", Config({Config.RETAIN_VISIBILITY: False}))

    assert (await adapter.visibility("b.txt")).visibility is Visibility.PUBLIC


async def test_a_move_carries_the_visibility_and_leaves_none_behind() -> None:
    adapter = InMemoryAdapter()
    await adapter.write("a.txt", b"x", Config({Config.VISIBILITY: Visibility.PRIVATE.value}))

    await adapter.move("a.txt", "b.txt", Config())

    assert (await adapter.visibility("b.txt")).visibility is Visibility.PRIVATE
    assert "a.txt" not in adapter._visibility


async def test_a_move_onto_the_same_path_keeps_the_visibility() -> None:
    adapter = InMemoryAdapter()
    await adapter.write("a.txt", b"x", Config({Config.VISIBILITY: Visibility.PRIVATE.value}))

    await adapter.move("a.txt", "a.txt", Config())

    assert (await adapter.visibility("a.txt")).visibility is Visibility.PRIVATE


async def test_deleting_a_file_forgets_its_visibility() -> None:
    adapter = InMemoryAdapter()
    await adapter.write("a.txt", b"x", Config({Config.VISIBILITY: Visibility.PRIVATE.value}))

    await adapter.delete("a.txt")

    assert adapter._visibility == {}


async def test_deleting_a_directory_forgets_everything_under_it() -> None:
    adapter = InMemoryAdapter()
    await adapter.write("d/a.txt", b"x", Config())
    await adapter.write("d/deeper/b.txt", b"y", Config())
    await adapter.write("elsewhere.txt", b"z", Config())

    await adapter.delete_directory("d")

    assert set(adapter._visibility) == {"elsewhere.txt"}


async def test_emptying_the_root_forgets_every_visibility() -> None:
    adapter = InMemoryAdapter()
    await adapter.write("a.txt", b"x", Config())
    await adapter.write("d/b.txt", b"y", Config())

    await adapter.delete_directory("")

    assert adapter._visibility == {}


async def test_the_visibility_of_a_missing_file_cannot_be_read() -> None:
    adapter = InMemoryAdapter()

    with pytest.raises(UnableToRetrieveMetadataError) as caught:
        _ = await adapter.visibility("missing.txt")

    assert caught.value.metadata_type == "visibility"
    assert caught.value.location == "missing.txt"


async def test_the_visibility_of_a_missing_file_cannot_be_set() -> None:
    adapter = InMemoryAdapter()

    with pytest.raises(UnableToSetVisibilityError) as caught:
        await adapter.set_visibility("missing.txt", Visibility.PRIVATE)

    assert caught.value.location == "missing.txt"


async def test_the_visibility_of_a_directory_cannot_be_set() -> None:
    adapter = InMemoryAdapter()
    await adapter.write("d/a.txt", b"x", Config())

    with pytest.raises(UnableToSetVisibilityError):
        await adapter.set_visibility("d", Visibility.PRIVATE)
