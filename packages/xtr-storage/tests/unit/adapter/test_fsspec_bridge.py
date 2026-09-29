# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnannotatedClassAttribute=false
# fsspec ships no type information; the fake below subclasses its untyped
# AsyncFileSystem and the real MemoryFileSystem it drives is untyped too, so the
# directives above are confined to this one test module.
"""The fsspec bridge dispatches by dialect and opens one session at most."""

from __future__ import annotations

import asyncio

import pytest
from fsspec.asyn import AsyncFileSystem
from fsspec.implementations.memory import MemoryFileSystem
from typing_extensions import override

from xtr_storage.adapter._fsspec_bridge import FsspecBridge

pytestmark = pytest.mark.anyio


def _memory_fs() -> MemoryFileSystem:
    """A memory filesystem whose store is its own, never the class-wide one."""
    fs = MemoryFileSystem(skip_instance_cache=True)
    fs.store = {}
    fs.pseudo_dirs = [""]
    return fs


async def test_it_round_trips_pipe_and_cat_over_a_memory_filesystem() -> None:
    bridge = FsspecBridge(_memory_fs())

    await bridge.pipe_file("/a.txt", b"hello world")

    assert await bridge.cat_file("/a.txt") == b"hello world"


async def test_it_reads_a_byte_range() -> None:
    bridge = FsspecBridge(_memory_fs())
    await bridge.pipe_file("/a.txt", b"hello world")

    assert await bridge.cat_file("/a.txt", start=0, end=5) == b"hello"


async def test_it_reports_info_for_a_file() -> None:
    bridge = FsspecBridge(_memory_fs())
    await bridge.pipe_file("/a.txt", b"hello")

    info = await bridge.info("/a.txt")

    assert info["type"] == "file"
    assert info["size"] == 5


async def test_it_lists_a_directory_in_detail() -> None:
    bridge = FsspecBridge(_memory_fs())
    await bridge.pipe_file("/dir/a.txt", b"a")
    await bridge.pipe_file("/dir/b.txt", b"bb")

    entries = await bridge.ls("/dir")

    names = sorted(str(entry["name"]) for entry in entries)
    assert names == ["/dir/a.txt", "/dir/b.txt"]


async def test_it_finds_a_tree_with_directories() -> None:
    bridge = FsspecBridge(_memory_fs())
    await bridge.pipe_file("/dir/sub/a.txt", b"a")

    found = await bridge.find("/dir", withdirs=True)

    assert "/dir/sub/a.txt" in found
    assert any(entry.get("type") == "directory" for entry in found.values())


async def test_it_removes_one_file() -> None:
    bridge = FsspecBridge(_memory_fs())
    await bridge.pipe_file("/a.txt", b"a")

    await bridge.rm_file("/a.txt")

    assert not await bridge.exists("/a.txt")


async def test_it_removes_a_tree_recursively() -> None:
    bridge = FsspecBridge(_memory_fs())
    await bridge.pipe_file("/dir/a.txt", b"a")
    await bridge.pipe_file("/dir/b.txt", b"b")

    await bridge.rm("/dir", recursive=True)

    assert not await bridge.exists("/dir/a.txt")
    assert not await bridge.exists("/dir/b.txt")


async def test_it_makes_a_directory() -> None:
    bridge = FsspecBridge(_memory_fs())

    await bridge.mkdir("/dir", create_parents=True)

    assert await bridge.info("/dir")


async def test_it_copies_a_file() -> None:
    bridge = FsspecBridge(_memory_fs())
    await bridge.pipe_file("/a.txt", b"payload")

    await bridge.cp_file("/a.txt", "/b.txt")

    assert await bridge.cat_file("/b.txt") == b"payload"


async def test_it_moves_a_file() -> None:
    bridge = FsspecBridge(_memory_fs())
    await bridge.pipe_file("/a.txt", b"payload")

    await bridge.mv("/a.txt", "/b.txt")

    assert await bridge.cat_file("/b.txt") == b"payload"
    assert not await bridge.exists("/a.txt")


async def test_it_answers_exists() -> None:
    bridge = FsspecBridge(_memory_fs())

    assert not await bridge.exists("/a.txt")
    await bridge.pipe_file("/a.txt", b"a")
    assert await bridge.exists("/a.txt")


async def test_it_lets_a_missing_path_raise_file_not_found() -> None:
    bridge = FsspecBridge(_memory_fs())

    with pytest.raises(FileNotFoundError):
        _ = await bridge.cat_file("/missing.txt")


async def test_it_dispatches_sync_through_to_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bridge = FsspecBridge(_memory_fs())
    calls = 0
    real_to_thread = asyncio.to_thread

    async def counting_to_thread(func, /, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003, ANN202
        nonlocal calls
        calls += 1
        return await real_to_thread(func, *args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", counting_to_thread)

    await bridge.pipe_file("/a.txt", b"a")

    assert calls == 1


class _FakeAsyncFileSystem(AsyncFileSystem):
    """A minimal asynchronous filesystem that counts its session openings.

    ``cachable = False`` because fsspec caches instances by their constructor
    arguments: two default ``_FakeAsyncFileSystem()`` calls would otherwise be
    one shared object, and one test's session count would leak into the next.
    """

    async_impl = True
    protocol = "fake"
    cachable = False

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(asynchronous=True, **kwargs)
        self.session_calls = 0
        self.store: dict[str, bytes] = {}

    async def set_session(self) -> object:
        # A real backend opens its client lazily under a lock; count the opens so
        # the test can prove exactly one happens under concurrent callers.
        await asyncio.sleep(0)
        self.session_calls += 1
        return object()

    @override
    async def _pipe_file(self, path, value, mode="overwrite", **kwargs) -> None:  # noqa: ANN001, ANN003
        del mode, kwargs
        self.store[path] = bytes(value)

    @override
    async def _cat_file(self, path, start=None, end=None, **kwargs) -> bytes:  # noqa: ANN001, ANN003
        del kwargs
        if path not in self.store:
            raise FileNotFoundError(path)
        return self.store[path][start:end]

    @override
    async def _exists(self, path, **kwargs) -> bool:  # noqa: ANN001, ANN003
        del kwargs
        return path in self.store


async def test_it_dispatches_async_through_underscore_methods() -> None:
    fs = _FakeAsyncFileSystem()
    bridge = FsspecBridge(fs)

    await bridge.pipe_file("/a.txt", b"async")

    assert await bridge.cat_file("/a.txt") == b"async"


async def test_it_opens_the_session_once_under_concurrent_calls() -> None:
    fs = _FakeAsyncFileSystem()
    bridge = FsspecBridge(fs)

    _ = await asyncio.gather(
        bridge.pipe_file("/a.txt", b"a"),
        bridge.pipe_file("/b.txt", b"b"),
        bridge.exists("/a.txt"),
    )

    assert fs.session_calls == 1


async def test_it_closes_the_session_once_and_is_idempotent() -> None:
    fs = _FakeAsyncFileSystem()
    closes = 0

    async def closer(closed_fs: object) -> None:
        nonlocal closes
        assert closed_fs is fs
        closes += 1

    bridge = FsspecBridge(fs, closer=closer)
    await bridge.pipe_file("/a.txt", b"a")

    await bridge.close()
    await bridge.close()

    assert closes == 1


async def test_it_does_not_close_when_no_session_was_created() -> None:
    calls = 0

    async def closer(_fs: object) -> None:
        nonlocal calls
        calls += 1

    bridge = FsspecBridge(_memory_fs(), closer=closer)
    await bridge.pipe_file("/a.txt", b"a")

    await bridge.close()

    assert calls == 0


async def test_the_call_escape_hatch_dispatches_async() -> None:
    fs = _FakeAsyncFileSystem()
    bridge = FsspecBridge(fs)
    await bridge.pipe_file("/a.txt", b"a")

    assert await bridge.call("exists", "/a.txt") is True


async def test_the_call_escape_hatch_dispatches_sync() -> None:
    bridge = FsspecBridge(_memory_fs())
    await bridge.pipe_file("/a.txt", b"a")

    assert await bridge.call("exists", "/a.txt") is True
