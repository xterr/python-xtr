# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false
# fsspec ships no type information; the memory filesystem these adapters build
# and the attributes they set on it are untyped, so the directives above are
# confined to this one module.
"""The base adapter's own behaviours, tested over a memory filesystem.

The conformance suite proves the base answers the contract; these tests pin the
behaviours the base owns beneath it — that it opens nothing until asked, streams
in bounded chunks, consults its hooks, and normalises whatever shape a backend
times a file in.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from fsspec.implementations.memory import MemoryFileSystem
from typing_extensions import override

from xtr_storage.adapter._fsspec_bridge import FsspecBridge
from xtr_storage.adapter.fsspec_adapter import FsspecAdapter
from xtr_storage.config import Config
from xtr_storage.exception import (
    FeatureNotSupportedError,
    UnableToDeleteDirectoryError,
    UnableToReadFileError,
    UnableToWriteFileError,
)
from xtr_storage.feature import Feature
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Mapping
    from pathlib import Path

    from fsspec import AbstractFileSystem

pytestmark = pytest.mark.anyio


class _MemoryAdapter(FsspecAdapter):
    """A base adapter over a memory filesystem with a store of its own."""

    @override
    def _create_filesystem(self) -> AbstractFileSystem:
        filesystem = MemoryFileSystem(skip_instance_cache=True)
        filesystem.store = {}
        filesystem.pseudo_dirs = [""]
        return filesystem


class _CountingAdapter(_MemoryAdapter):
    """Counts how many times its filesystem is built."""

    def __init__(self) -> None:
        super().__init__()
        self.builds: int = 0

    @override
    def _create_filesystem(self) -> AbstractFileSystem:
        self.builds += 1
        return super()._create_filesystem()


class _RecordingWriteOptions(_MemoryAdapter):
    """Records the config each write hands its write-options hook."""

    def __init__(self) -> None:
        super().__init__()
        self.seen: list[Config] = []

    @override
    def _write_options(self, config: Config) -> Mapping[str, object]:
        self.seen.append(config)
        return {}


class _MarkerHiding(_MemoryAdapter):
    """Hides any listed entry whose name ends in the marker suffix."""

    @override
    def _is_hidden_entry(self, path: str) -> bool:
        return path.endswith(".marker")


async def test_constructing_the_adapter_opens_no_filesystem() -> None:
    adapter = _MemoryAdapter()

    assert adapter._bridge is None


async def test_the_first_operation_builds_the_filesystem_once() -> None:
    adapter = _CountingAdapter()

    await adapter.write("a.txt", b"a", Config())
    _ = await adapter.read("a.txt")

    assert adapter.builds == 1
    assert adapter._bridge is not None


async def test_read_stream_chunks_by_chunk_size(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("xtr_storage.adapter.fsspec_adapter.CHUNK_SIZE", 4)
    adapter = _MemoryAdapter()
    await adapter.write("big.txt", b"0123456789", Config())

    chunks = [chunk async for chunk in adapter.read_stream("big.txt")]

    assert chunks == [b"0123", b"4567", b"89"]
    assert b"".join(chunks) == b"0123456789"


async def test_the_write_options_hook_receives_the_write_config() -> None:
    adapter = _RecordingWriteOptions()
    config = Config({Config.VISIBILITY: Visibility.PUBLIC.value})

    await adapter.write("a.txt", b"a", config)

    assert adapter.seen == [config]


async def test_hidden_entries_are_skipped_in_listings() -> None:
    adapter = _MarkerHiding()
    await adapter.write("visible.txt", b"a", Config())
    await adapter.write("secret.marker", b"b", Config())

    paths = {entry.path async for entry in adapter.list_contents("", deep=False)}

    assert "visible.txt" in paths
    assert "secret.marker" not in paths


async def test_closing_before_any_use_is_safe() -> None:
    adapter = _MemoryAdapter()

    await adapter.close()

    assert adapter._bridge is None


async def test_set_visibility_names_the_adapter_and_feature() -> None:
    adapter = _MemoryAdapter()

    with pytest.raises(FeatureNotSupportedError) as caught:
        await adapter.set_visibility("a.txt", Visibility.PUBLIC)

    assert caught.value.adapter == "_MemoryAdapter"
    assert caught.value.feature is Feature.VISIBILITY


def test_epoch_reads_the_most_specific_key_first() -> None:
    assert FsspecAdapter._epoch({"mtime": 5, "created": 9}) == 5


def test_epoch_normalizes_a_float() -> None:
    assert FsspecAdapter._epoch({"mtime": 100.9}) == 100


def test_epoch_normalizes_a_datetime() -> None:
    moment = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)

    assert FsspecAdapter._epoch({"updated": moment}) == int(moment.timestamp())


def test_epoch_normalizes_an_iso_string() -> None:
    assert FsspecAdapter._epoch({"created": "2026-01-02T03:04:05+00:00"}) == int(
        datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC).timestamp()
    )


def test_epoch_is_none_when_nothing_parses() -> None:
    assert FsspecAdapter._epoch({}) is None
    assert FsspecAdapter._epoch({"mtime": "not a date"}) is None
    assert FsspecAdapter._epoch({"mtime": True}) is None


def test_content_type_reads_the_backends_own_key() -> None:
    assert FsspecAdapter._content_type({"ContentType": "image/png"}) == "image/png"
    assert FsspecAdapter._content_type({"contentType": "text/plain"}) == "text/plain"
    assert FsspecAdapter._content_type({"content_type": "application/json"}) == "application/json"


def test_content_type_is_none_when_absent_or_empty() -> None:
    assert FsspecAdapter._content_type({}) is None
    assert FsspecAdapter._content_type({"ContentType": ""}) is None


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    """Yield the given chunks, as the async source a streamed write takes."""
    for chunk in chunks:
        yield chunk


async def _breaking_stream() -> AsyncIterator[bytes]:
    """Yield enough to spill to a temp, then fail as a socket read would."""
    yield b"01234567"
    raise OSError("the source stream broke")


async def test_read_stream_refuses_a_file_the_backend_gives_no_size(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _MemoryAdapter()
    await adapter.write("sizeless.txt", b"payload", Config())

    async def info_without_size(self: FsspecBridge, path: str) -> dict[str, object]:
        del self, path
        return {"type": "file"}

    monkeypatch.setattr(FsspecBridge, "info", info_without_size)

    with pytest.raises(UnableToReadFileError):
        async for _chunk in adapter.read_stream("sizeless.txt"):
            pass


async def test_a_small_stream_is_written_in_one_piece() -> None:
    adapter = _MemoryAdapter()

    await adapter.write_stream("small.txt", _stream(b"foo", b"bar"), Config())

    assert await adapter.read("small.txt") == b"foobar"


async def test_a_stream_past_the_spool_limit_spills_through_a_temp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("xtr_storage.adapter.fsspec_adapter._SPOOL_MAX_SIZE", 4)
    adapter = _MemoryAdapter()
    payload = b"0123456789abcdef"

    await adapter.write_stream("big.txt", _stream(b"0123", b"456789ab", b"cdef"), Config())

    assert await adapter.read("big.txt") == payload


async def test_a_spilled_stream_leaves_no_temporary_file_behind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("xtr_storage.adapter.fsspec_adapter._SPOOL_MAX_SIZE", 4)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    adapter = _MemoryAdapter()

    await adapter.write_stream("big.txt", _stream(b"0123", b"4567"), Config())

    remaining = await asyncio.to_thread(lambda: list(tmp_path.iterdir()))
    assert remaining == []


async def test_a_source_that_breaks_after_spilling_leaves_no_temporary_file_behind(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("xtr_storage.adapter.fsspec_adapter._SPOOL_MAX_SIZE", 4)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    adapter = _MemoryAdapter()

    with pytest.raises(UnableToWriteFileError):
        await adapter.write_stream("big.txt", _breaking_stream(), Config())

    remaining = await asyncio.to_thread(lambda: list(tmp_path.iterdir()))
    assert remaining == []


async def test_a_same_path_copy_reaches_the_backend() -> None:
    adapter = _MemoryAdapter()
    await adapter.write("x.txt", b"keep", Config())
    real_cp_file = FsspecBridge.cp_file
    calls: list[tuple[str, str]] = []

    async def recording_cp_file(self: FsspecBridge, src: str, dst: str, **kwargs: object) -> None:
        calls.append((src, dst))
        await real_cp_file(self, src, dst, **kwargs)

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(FsspecBridge, "cp_file", recording_cp_file)
        await adapter.copy("x.txt", "x.txt", Config())

    assert calls == [("x.txt", "x.txt")]
    assert await adapter.read("x.txt") == b"keep"


async def test_deleting_the_storage_root_is_refused() -> None:
    adapter = _MemoryAdapter()
    await adapter.write("kept.txt", b"a", Config())

    with pytest.raises(UnableToDeleteDirectoryError):
        await adapter.delete_directory("")

    assert await adapter.file_exists("kept.txt")
