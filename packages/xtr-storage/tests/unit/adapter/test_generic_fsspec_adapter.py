# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportUnknownParameterType=false, reportAttributeAccessIssue=false
# fsspec ships no type information; the memory filesystem this module builds,
# the methods it notes calls on and the attributes it sets are all untyped, so
# the directives above are confined to this one module.
"""What the generic adapter owns: somebody else's filesystem, used as given.

The conformance suite proves it behaves like every other backend. These tests
pin what is particular to it — that the instance it is handed is the one it
speaks to, that it touches nothing until asked, that a root keeps the caller's
paths relative, and that it refuses a visibility it has no way to know about.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from fsspec.implementations.memory import MemoryFileSystem
from typing_extensions import override

from xtr_storage.adapter.generic_fsspec_adapter import GenericFsspecAdapter
from xtr_storage.config import Config
from xtr_storage.exception import FeatureNotSupportedError
from xtr_storage.feature import Feature
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from xtr_storage.storage_attributes import StorageAttributes

pytestmark = pytest.mark.anyio


@final
class _RecordingFileSystem(MemoryFileSystem):
    """A memory filesystem of its own that notes the writes made on it.

    ``cachable`` is off because fsspec hands back a cached instance for equal
    constructor arguments, which would give two tests one filesystem carrying
    the calls of both. Turning it off on the class is the only moment early
    enough: the cache is consulted before the constructor runs.
    """

    cachable = False

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []
        self.store = {}
        self.pseudo_dirs = [""]

    @override
    def pipe_file(self, path: str, value: bytes, mode: str = "overwrite", **kwargs: object) -> None:
        self.calls.append("pipe_file")
        super().pipe_file(path, value, mode, **kwargs)


def _memory_filesystem() -> MemoryFileSystem:
    """Build a memory filesystem whose files belong to one test alone."""
    filesystem = MemoryFileSystem(skip_instance_cache=True)
    filesystem.store = {}
    filesystem.pseudo_dirs = [""]
    return filesystem


async def _entries(adapter: GenericFsspecAdapter, path: str = "") -> list[StorageAttributes]:
    """Drain a shallow listing into a list."""
    return [entry async for entry in adapter.list_contents(path, deep=False)]


async def test_constructing_the_adapter_calls_nothing_on_the_filesystem() -> None:
    filesystem = _RecordingFileSystem()

    adapter = GenericFsspecAdapter(filesystem)

    assert filesystem.calls == []
    assert adapter._bridge is None


async def test_the_first_operation_reaches_the_filesystem_it_was_given() -> None:
    filesystem = _RecordingFileSystem()
    adapter = GenericFsspecAdapter(filesystem)

    await adapter.write("a.txt", b"x", Config())

    assert filesystem.calls == ["pipe_file"]
    assert await adapter.read("a.txt") == b"x"


async def test_a_root_is_where_the_files_land() -> None:
    filesystem = _memory_filesystem()
    adapter = GenericFsspecAdapter(filesystem, "under/here")

    await adapter.write("a.txt", b"x", Config())

    assert "/under/here/a.txt" in filesystem.store


async def test_a_root_stays_out_of_the_paths_a_listing_reports() -> None:
    adapter = GenericFsspecAdapter(_memory_filesystem(), "under/here")
    await adapter.write("a.txt", b"x", Config())
    await adapter.write("nested/b.txt", b"y", Config())

    paths = {entry.path for entry in await _entries(adapter)}

    assert paths == {"a.txt", "nested"}


async def test_a_root_stays_out_of_the_paths_a_deep_listing_reports() -> None:
    adapter = GenericFsspecAdapter(_memory_filesystem(), "under/here")
    await adapter.write("nested/b.txt", b"y", Config())

    paths = {entry.path async for entry in adapter.list_contents("", deep=True)}

    assert paths == {"nested", "nested/b.txt"}


async def test_two_roots_on_one_filesystem_do_not_see_each_other() -> None:
    filesystem = _memory_filesystem()
    first = GenericFsspecAdapter(filesystem, "first")
    second = GenericFsspecAdapter(filesystem, "second")

    await first.write("a.txt", b"x", Config())

    assert not await second.file_exists("a.txt")


async def test_setting_a_visibility_is_not_supported() -> None:
    adapter = GenericFsspecAdapter(_memory_filesystem())
    await adapter.write("a.txt", b"x", Config())

    with pytest.raises(FeatureNotSupportedError) as caught:
        await adapter.set_visibility("a.txt", Visibility.PUBLIC)

    assert caught.value.adapter == "GenericFsspecAdapter"
    assert caught.value.feature is Feature.VISIBILITY


async def test_reading_a_visibility_is_not_supported() -> None:
    adapter = GenericFsspecAdapter(_memory_filesystem())
    await adapter.write("a.txt", b"x", Config())

    with pytest.raises(FeatureNotSupportedError):
        _ = await adapter.visibility("a.txt")


async def test_a_copy_asked_for_a_visibility_says_so() -> None:
    adapter = GenericFsspecAdapter(_memory_filesystem())
    await adapter.write("a.txt", b"x", Config())

    with pytest.raises(FeatureNotSupportedError):
        await adapter.copy("a.txt", "b.txt", Config({Config.VISIBILITY: Visibility.PUBLIC.value}))


async def test_a_copy_that_would_only_keep_a_visibility_goes_ahead_without_one() -> None:
    adapter = GenericFsspecAdapter(_memory_filesystem())
    await adapter.write("a.txt", b"x", Config())

    await adapter.copy("a.txt", "b.txt", Config())

    assert await adapter.read("b.txt") == b"x"


async def test_closing_the_adapter_leaves_the_filesystem_usable() -> None:
    filesystem = _memory_filesystem()
    adapter = GenericFsspecAdapter(filesystem)
    await adapter.write("a.txt", b"x", Config())

    await adapter.close()

    assert filesystem.cat_file("/a.txt") == b"x"
