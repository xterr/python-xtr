"""What every adapter must do, as a test class an adapter's own tests inherit.

An adapter's test class inherits :class:`AdapterConformance` and defines an
``adapter`` fixture yielding a fresh adapter and closing it when the test ends.
It sets ``supports_visibility`` to say whether the backend has a notion of who
may read a file, and ``http_fetch`` to say whether a public or temporary URL it
hands out can be fetched over HTTP in the test environment.

The behaviours here are the contract every backend answers the same way:
reading what was written, listing what is there, refusing what is not, and
raising the one right error when a file is missing. Capability behaviours —
checksums, public and temporary URLs — run only against an adapter that offers
them, discovered at runtime with :func:`isinstance` rather than a marker.
"""

from __future__ import annotations

import asyncio
import time
import urllib.request
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, ClassVar

import pytest

from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    FeatureNotSupportedError,
    UnableToCopyFileError,
    UnableToMoveFileError,
    UnableToReadFileError,
    UnableToRetrieveMetadataError,
)
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
    from xtr_storage.storage_attributes import StorageAttributes

__all__ = ["AdapterConformance"]

_WITHIN_SECONDS = 30


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    """Yield the given chunks in order, as the async source a write takes."""
    for chunk in chunks:
        yield chunk


async def _entries(
    adapter: StorageAdapterInterface,
    path: str = "",
    *,
    deep: bool = False,
) -> list[StorageAttributes]:
    """Drain a listing into a list, for a test that asserts on the whole of it."""
    return [entry async for entry in adapter.list_contents(path, deep)]


def _fetch(url: str) -> bytes:
    """Fetch a URL the adapter just generated, for the HTTP round-trip tests."""
    # urllib types its return as Any in the standard stubs, so the reads below
    # are untyped however they are written; the S310 URL is one the adapter under
    # test produced, not caller input.
    with urllib.request.urlopen(url) as response:  # noqa: S310  # pyright: ignore[reportAny]
        return bytes(response.read())  # pyright: ignore[reportAny]


class AdapterConformance:
    """Reading, writing, listing, moving and metadata, for any adapter."""

    pytestmark: ClassVar[pytest.MarkDecorator] = pytest.mark.anyio
    supports_visibility: ClassVar[bool]
    http_fetch: ClassVar[bool] = False

    async def test_it_reads_back_what_it_wrote(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write("hello.txt", b"hello world", Config())

        assert await adapter.read("hello.txt") == b"hello world"

    async def test_it_writes_from_a_stream(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write_stream("streamed.txt", _stream(b"foo", b"bar"), Config())

        assert await adapter.read("streamed.txt") == b"foobar"

    async def test_it_writes_an_empty_stream(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write_stream("empty.txt", _stream(), Config())

        assert await adapter.read("empty.txt") == b""

    async def test_it_reads_a_stream(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write("chunked.txt", b"streamed bytes", Config())

        chunks = [chunk async for chunk in adapter.read_stream("chunked.txt")]

        assert b"".join(chunks) == b"streamed bytes"

    async def test_it_handles_special_characters_in_names(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        name = "we ird/[a] {b} c.txt"

        await adapter.write(name, b"payload", Config())

        assert await adapter.read(name) == b"payload"
        assert await adapter.file_exists(name)
        assert any(entry.path == name for entry in await _entries(adapter, "we ird"))

    async def test_it_treats_a_directory_named_zero_as_a_directory(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("0/file.txt", b"zero", Config())

        assert await adapter.directory_exists("0")
        assert any(entry.path == "0" and entry.is_dir for entry in await _entries(adapter))

    async def test_it_overwrites_an_existing_file(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("target.txt", b"first", Config())
        await adapter.write("target.txt", b"second", Config())

        assert await adapter.read("target.txt") == b"second"

    async def test_it_follows_a_files_existence_through_its_life(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        assert not await adapter.file_exists("life.txt")
        await adapter.write("life.txt", b"a", Config())
        assert await adapter.file_exists("life.txt")
        await adapter.delete("life.txt")
        assert not await adapter.file_exists("life.txt")

    async def test_it_lists_a_directory_shallowly(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("top.txt", b"a", Config())
        await adapter.write("sub/inner.txt", b"b", Config())

        by_path = {entry.path: entry for entry in await _entries(adapter)}

        assert by_path["top.txt"].is_file
        assert by_path["sub"].is_dir

    async def test_it_lists_a_tree_deeply(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write("d/a.txt", b"a", Config())
        await adapter.write("d/e/b.txt", b"b", Config())

        paths = {entry.path for entry in await _entries(adapter, deep=True)}

        assert {"d", "d/a.txt", "d/e", "d/e/b.txt"} <= paths

    async def test_it_lists_the_top_level(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write("root.txt", b"a", Config())

        assert any(entry.path == "root.txt" for entry in await _entries(adapter))

    async def test_a_directory_is_absent_present_and_gone_in_turn(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        assert not await adapter.directory_exists("nowhere")
        await adapter.write("dir/f.txt", b"a", Config())
        assert await adapter.directory_exists("dir")
        await adapter.create_directory("made", Config())
        assert await adapter.directory_exists("made")
        await adapter.delete_directory("made")
        assert not await adapter.directory_exists("made")

    async def test_a_file_is_not_a_directory(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write("plain.txt", b"a", Config())

        assert not await adapter.directory_exists("plain.txt")

    async def test_a_directory_is_not_a_file(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write("folder/f.txt", b"a", Config())

        assert not await adapter.file_exists("folder")

    async def test_it_reports_a_files_size(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write("sized.txt", b"12345", Config())

        assert (await adapter.file_size("sized.txt")).file_size == 5

    async def test_it_reports_a_recent_last_modified(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("recent.txt", b"a", Config())

        moment = (await adapter.last_modified("recent.txt")).last_modified

        assert moment is not None
        assert abs(time.time() - moment) < _WITHIN_SECONDS

    async def test_it_reports_an_svg_mime_type(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write("logo.svg", b"<svg></svg>", Config())

        assert (await adapter.mime_type("logo.svg")).mime_type == "image/svg+xml"

    async def test_an_unknown_extension_has_no_mime_type(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("data.md5", b"abc", Config())

        with pytest.raises(UnableToRetrieveMetadataError):
            _ = await adapter.mime_type("data.md5")

    async def test_the_size_of_a_directory_cannot_be_read(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("szdir/f.txt", b"a", Config())

        with pytest.raises(UnableToRetrieveMetadataError):
            _ = await adapter.file_size("szdir")

    async def test_metadata_of_a_missing_file_raises(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        with pytest.raises(UnableToRetrieveMetadataError):
            _ = await adapter.file_size("missing.txt")
        with pytest.raises(UnableToRetrieveMetadataError):
            _ = await adapter.last_modified("missing.txt")
        with pytest.raises(UnableToRetrieveMetadataError):
            _ = await adapter.mime_type("missing.txt")

    async def test_reading_a_missing_file_raises(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        with pytest.raises(UnableToReadFileError):
            _ = await adapter.read("missing.txt")
        with pytest.raises(UnableToReadFileError):
            async for _chunk in adapter.read_stream("missing.txt"):
                pass

    async def test_deleting_a_missing_file_is_silent(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.delete("ghost.txt")

    async def test_it_copies_content(self, adapter: StorageAdapterInterface) -> None:
        write_config = (
            Config({Config.VISIBILITY: Visibility.PUBLIC.value})
            if self.supports_visibility
            else Config()
        )
        await adapter.write("src.txt", b"hello", write_config)

        await adapter.copy("src.txt", "dst.txt", Config())

        assert await adapter.read("dst.txt") == b"hello"
        source_mime = (await adapter.mime_type("src.txt")).mime_type
        assert (await adapter.mime_type("dst.txt")).mime_type == source_mime
        if self.supports_visibility:
            assert (await adapter.visibility("dst.txt")).visibility == Visibility.PUBLIC

    async def test_copying_a_missing_file_raises(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        with pytest.raises(UnableToCopyFileError):
            await adapter.copy("nope.txt", "dest.txt", Config())

    async def test_it_copies_twice_from_one_source(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("c.txt", b"data", Config())

        await adapter.copy("c.txt", "c1.txt", Config())
        await adapter.copy("c.txt", "c2.txt", Config())

        assert await adapter.read("c1.txt") == b"data"
        assert await adapter.read("c2.txt") == b"data"

    async def test_a_copy_overwrites_the_destination(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("from.txt", b"new", Config())
        await adapter.write("onto.txt", b"old", Config())

        await adapter.copy("from.txt", "onto.txt", Config())

        assert await adapter.read("onto.txt") == b"new"

    async def test_a_copy_to_the_same_path_keeps_the_content(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("same.txt", b"keep", Config())

        await adapter.copy("same.txt", "same.txt", Config())

        assert await adapter.read("same.txt") == b"keep"

    async def test_it_moves_a_file(self, adapter: StorageAdapterInterface) -> None:
        await adapter.write("m1.txt", b"data", Config())

        await adapter.move("m1.txt", "m2.txt", Config())

        assert await adapter.read("m2.txt") == b"data"
        assert not await adapter.file_exists("m1.txt")

    async def test_moving_a_missing_file_raises(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        with pytest.raises(UnableToMoveFileError):
            await adapter.move("nope.txt", "dest.txt", Config())

    async def test_a_move_overwrites_the_destination(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("mfrom.txt", b"fresh", Config())
        await adapter.write("monto.txt", b"stale", Config())

        await adapter.move("mfrom.txt", "monto.txt", Config())

        assert await adapter.read("monto.txt") == b"fresh"

    async def test_a_move_to_the_same_path_keeps_the_content(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("stay.txt", b"kept", Config())

        await adapter.move("stay.txt", "stay.txt", Config())

        assert await adapter.read("stay.txt") == b"kept"

    async def test_creating_a_directory_twice_leaves_one(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.create_directory("once", Config())
        await adapter.create_directory("once", Config())

        directories = [
            entry for entry in await _entries(adapter) if entry.is_dir and entry.path == "once"
        ]

        assert len(directories) == 1

    async def test_visibility_round_trips_or_is_unsupported(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        await adapter.write("v.txt", b"x", Config())

        if not self.supports_visibility:
            with pytest.raises(FeatureNotSupportedError):
                await adapter.set_visibility("v.txt", Visibility.PUBLIC)
            return

        await adapter.set_visibility("v.txt", Visibility.PRIVATE)
        assert (await adapter.visibility("v.txt")).visibility == Visibility.PRIVATE
        await adapter.set_visibility("v.txt", Visibility.PUBLIC)
        assert (await adapter.visibility("v.txt")).visibility == Visibility.PUBLIC

    async def test_visibility_of_a_missing_file_raises_when_supported(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        if not self.supports_visibility:
            pytest.skip("adapter has no notion of visibility")

        with pytest.raises(UnableToRetrieveMetadataError):
            _ = await adapter.visibility("missing.txt")

    async def test_it_provides_a_checksum_when_supported(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        if not isinstance(adapter, ChecksumProviderInterface):
            pytest.skip("adapter provides no checksum")
        await adapter.write("checked.txt", b"digest me", Config())

        try:
            digest = await adapter.checksum("checked.txt", Config())
        except ChecksumAlgorithmNotSupportedError:
            pytest.skip("adapter keeps no digest of the default algorithm")

        assert digest != ""

    async def test_it_generates_a_public_url_when_supported(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        if not isinstance(adapter, PublicUrlGeneratorInterface):
            pytest.skip("adapter generates no public url")
        await adapter.write("pub.txt", b"public bytes", Config())

        url = await adapter.public_url("pub.txt", Config())

        assert url.startswith(("http://", "https://"))
        if self.http_fetch:
            assert await asyncio.to_thread(_fetch, url) == b"public bytes"

    async def test_it_generates_a_temporary_url_when_supported(
        self,
        adapter: StorageAdapterInterface,
    ) -> None:
        if not isinstance(adapter, TemporaryUrlGeneratorInterface):
            pytest.skip("adapter signs no temporary url")
        await adapter.write("temp.txt", b"temporary bytes", Config())
        expires_at = datetime.now(UTC) + timedelta(minutes=5)

        url = await adapter.temporary_url("temp.txt", expires_at, Config())

        assert url.startswith(("http://", "https://"))
        if self.http_fetch:
            assert await asyncio.to_thread(_fetch, url) == b"temporary bytes"
