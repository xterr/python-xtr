"""What the local adapter adds to the shared base, on a real directory.

The whole adapter contract is proved elsewhere, against the conformance suite;
these tests pin the three things only a real filesystem has. That nothing is
created until something is written — an application may declare a storage for a
disk it never touches. That permissions are the exact ones asked for rather than
whatever the process umask leaves. And that a symbolic link, which could lead
anywhere, is either left out of a listing or refused.
"""

from __future__ import annotations

import stat
from typing import TYPE_CHECKING

import pytest

from xtr_storage.adapter.local_adapter import LocalAdapter
from xtr_storage.adapter.portable_visibility_converter import PortableVisibilityConverter
from xtr_storage.config import Config
from xtr_storage.exception import (
    SymbolicLinkEncounteredError,
    UnableToCreateDirectoryError,
    UnableToRetrieveMetadataError,
    UnableToSetVisibilityError,
    UnableToWriteFileError,
)
from xtr_storage.link_handling import LinkHandling
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

    from xtr_storage.storage_attributes import StorageAttributes

pytestmark = pytest.mark.anyio


def _mode(path: Path) -> int:
    """Return a path's permission bits, with the bits saying what it is removed."""
    return stat.S_IMODE(path.stat().st_mode)


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    """Yield the given chunks, as the async source a streamed write takes."""
    for chunk in chunks:
        yield chunk


async def _paths(adapter: LocalAdapter, path: str = "", *, deep: bool = False) -> set[str]:
    """Drain a listing into the set of paths it named."""
    return {entry.path async for entry in adapter.list_contents(path, deep)}


async def _entries(adapter: LocalAdapter, *, deep: bool = False) -> list[StorageAttributes]:
    """Drain a listing, for a test that asserts a link raised before it finished."""
    return [entry async for entry in adapter.list_contents("", deep)]


async def test_constructing_the_adapter_creates_no_directory(tmp_path: Path) -> None:
    root = tmp_path / "root"

    adapter = LocalAdapter(root)

    assert not root.exists()
    assert adapter._bridge is None


async def test_closing_an_unused_adapter_creates_no_directory(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)

    await adapter.close()

    assert not root.exists()


async def test_the_root_is_created_by_the_first_write(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)

    await adapter.write("first.txt", b"bytes", Config())

    assert (root / "first.txt").read_bytes() == b"bytes"


async def test_a_relative_directory_is_resolved_so_listings_strip_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    adapter = LocalAdapter("store")

    await adapter.write("inside.txt", b"a", Config())

    assert (tmp_path / "store" / "inside.txt").exists()
    assert await _paths(adapter) == {"inside.txt"}


async def test_the_directories_a_write_makes_are_private_by_default(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)

    await adapter.write("deep/deeper/file.txt", b"a", Config())

    assert _mode(root) == 0o700
    assert _mode(root / "deep") == 0o700
    assert _mode(root / "deep" / "deeper") == 0o700


async def test_a_write_takes_the_directory_visibility_it_is_given(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)

    await adapter.write(
        "shared/file.txt",
        b"a",
        Config({Config.DIRECTORY_VISIBILITY: Visibility.PUBLIC.value}),
    )

    assert _mode(root) == 0o755
    assert _mode(root / "shared") == 0o755


async def test_a_public_write_lands_on_the_public_file_mode(tmp_path: Path) -> None:
    adapter = LocalAdapter(tmp_path / "root")

    await adapter.write("open.txt", b"a", Config({Config.VISIBILITY: Visibility.PUBLIC.value}))

    assert _mode(tmp_path / "root" / "open.txt") == 0o644


async def test_a_private_write_lands_on_the_private_file_mode(tmp_path: Path) -> None:
    adapter = LocalAdapter(tmp_path / "root")

    await adapter.write("shut.txt", b"a", Config({Config.VISIBILITY: Visibility.PRIVATE.value}))

    assert _mode(tmp_path / "root" / "shut.txt") == 0o600


async def test_a_streamed_write_is_given_the_same_treatment(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)

    await adapter.write_stream(
        "streamed/file.txt",
        _stream(b"foo", b"bar"),
        Config({Config.VISIBILITY: Visibility.PUBLIC.value}),
    )

    assert await adapter.read("streamed/file.txt") == b"foobar"
    assert _mode(root / "streamed") == 0o700
    assert _mode(root / "streamed" / "file.txt") == 0o644


async def test_a_write_without_a_visibility_leaves_the_filesystems_own_mode(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)

    await adapter.write("written.txt", b"a", Config())

    reference = root / "reference.txt"
    _ = reference.write_bytes(b"a")
    assert _mode(root / "written.txt") == _mode(reference)


async def test_a_created_directory_is_private_by_default(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)

    await adapter.create_directory("made", Config())

    assert _mode(root / "made") == 0o700


async def test_a_created_directory_takes_the_visibility_it_is_given(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)

    await adapter.create_directory(
        "open", Config({Config.DIRECTORY_VISIBILITY: Visibility.PUBLIC.value})
    )

    assert _mode(root / "open") == 0o755


async def test_creating_a_directory_again_leaves_its_mode_alone(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)
    await adapter.create_directory(
        "kept", Config({Config.DIRECTORY_VISIBILITY: Visibility.PUBLIC.value})
    )

    await adapter.create_directory(
        "kept", Config({Config.DIRECTORY_VISIBILITY: Visibility.PRIVATE.value})
    )

    assert _mode(root / "kept") == 0o755


async def test_creating_a_directory_where_a_file_is_fails(tmp_path: Path) -> None:
    adapter = LocalAdapter(tmp_path / "root")
    await adapter.write("occupied", b"a", Config())

    with pytest.raises(UnableToCreateDirectoryError):
        await adapter.create_directory("occupied", Config())


async def test_writing_below_a_file_fails_as_a_write(tmp_path: Path) -> None:
    adapter = LocalAdapter(tmp_path / "root")
    await adapter.write("blocking", b"a", Config())

    with pytest.raises(UnableToWriteFileError):
        await adapter.write("blocking/child.txt", b"b", Config())


async def test_a_visibility_round_trips_through_the_filesystem(tmp_path: Path) -> None:
    adapter = LocalAdapter(tmp_path / "root")
    await adapter.write("v.txt", b"a", Config())

    await adapter.set_visibility("v.txt", Visibility.PRIVATE)
    assert (await adapter.visibility("v.txt")).visibility is Visibility.PRIVATE
    assert _mode(tmp_path / "root" / "v.txt") == 0o600

    await adapter.set_visibility("v.txt", Visibility.PUBLIC)
    assert (await adapter.visibility("v.txt")).visibility is Visibility.PUBLIC
    assert _mode(tmp_path / "root" / "v.txt") == 0o644


async def test_a_directorys_visibility_uses_the_directory_modes(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)
    await adapter.create_directory("d", Config())

    await adapter.set_visibility("d", Visibility.PUBLIC)

    assert _mode(root / "d") == 0o755
    assert (await adapter.visibility("d")).visibility is Visibility.PUBLIC


async def test_the_visibility_of_a_missing_file_cannot_be_read(tmp_path: Path) -> None:
    adapter = LocalAdapter(tmp_path / "root")

    with pytest.raises(UnableToRetrieveMetadataError) as caught:
        _ = await adapter.visibility("ghost.txt")

    assert caught.value.metadata_type == "visibility"


async def test_the_visibility_of_a_missing_file_cannot_be_set(tmp_path: Path) -> None:
    adapter = LocalAdapter(tmp_path / "root")

    with pytest.raises(UnableToSetVisibilityError) as caught:
        await adapter.set_visibility("ghost.txt", Visibility.PUBLIC)

    assert caught.value.location == "ghost.txt"


async def test_the_converter_it_was_built_with_decides_every_mode(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(
        root,
        visibility=PortableVisibilityConverter(
            file_public=0o664,
            directory_public=0o775,
            default_for_directories=Visibility.PUBLIC,
        ),
    )

    await adapter.write("group.txt", b"a", Config({Config.VISIBILITY: Visibility.PUBLIC.value}))

    assert _mode(root) == 0o775
    assert _mode(root / "group.txt") == 0o664


async def test_a_skipping_listing_leaves_a_linked_file_out(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root, link_handling=LinkHandling.SKIP)
    await adapter.write("real.txt", b"a", Config())
    (root / "link.txt").symlink_to(root / "real.txt")

    assert await _paths(adapter) == {"real.txt"}


async def test_a_skipping_listing_leaves_a_linked_directory_out(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root, link_handling=LinkHandling.SKIP)
    await adapter.create_directory("real", Config())
    (root / "link").symlink_to(root / "real", target_is_directory=True)

    assert await _paths(adapter) == {"real"}


async def test_a_refusing_listing_raises_on_a_linked_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root, link_handling=LinkHandling.DISALLOW)
    await adapter.write("real.txt", b"a", Config())
    (root / "link.txt").symlink_to(root / "real.txt")

    with pytest.raises(SymbolicLinkEncounteredError) as caught:
        _ = await _entries(adapter)

    assert caught.value.location == "link.txt"


async def test_a_refusing_deep_listing_raises_on_a_linked_file(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root, link_handling=LinkHandling.DISALLOW)
    await adapter.write("tree/real.txt", b"a", Config())
    (root / "tree" / "link.txt").symlink_to(root / "tree" / "real.txt")

    with pytest.raises(SymbolicLinkEncounteredError) as caught:
        _ = await _entries(adapter, deep=True)

    assert caught.value.location == "tree/link.txt"


async def test_refusing_links_is_the_default(tmp_path: Path) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root)
    await adapter.write("real.txt", b"a", Config())
    (root / "link.txt").symlink_to(root / "real.txt")

    with pytest.raises(SymbolicLinkEncounteredError):
        _ = await _entries(adapter)


async def test_a_listing_of_ordinary_entries_is_untouched_by_link_handling(
    tmp_path: Path,
) -> None:
    root = tmp_path / "root"
    adapter = LocalAdapter(root, link_handling=LinkHandling.DISALLOW)
    await adapter.write("plain.txt", b"a", Config())
    await adapter.write("sub/nested.txt", b"b", Config())

    assert await _paths(adapter) == {"plain.txt", "sub"}
    assert await _paths(adapter, deep=True) == {"plain.txt", "sub", "sub/nested.txt"}
