"""What the local adapter adds to the shared base, on a real directory.

The whole adapter contract is proved elsewhere, against the conformance suite;
these tests pin the three things only a real filesystem has. That nothing is
created until something is written — an application may declare a storage for a
disk it never touches. That permissions are the exact ones asked for rather than
whatever the process umask leaves. And that a symbolic link, which could lead
anywhere, is either left out of a listing or refused.
"""

from __future__ import annotations

import errno
import os
import stat
from typing import TYPE_CHECKING

import pytest

from xtr_storage.adapter.local_adapter import LocalAdapter, _make_directories
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


def _link_out_of_root(tmp_path: Path, link_handling: LinkHandling) -> tuple[LocalAdapter, Path]:
    """Build an adapter whose root holds a link to a file outside it.

    Parametrized over every way of handling a link, because none of them
    follows one out of the root: skipping hides a link from a listing, it does
    not make the tree above the root reachable through it.
    """
    outside = tmp_path / "outside.txt"
    _ = outside.write_bytes(b"secret")
    root = tmp_path / "root"
    root.mkdir()
    (root / "escape.txt").symlink_to(outside)
    return LocalAdapter(root, link_handling=link_handling), outside


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_reading_through_an_escaping_link_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter, _outside = _link_out_of_root(tmp_path, link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        _ = await adapter.read("escape.txt")


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_streaming_a_read_through_an_escaping_link_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter, _outside = _link_out_of_root(tmp_path, link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        async for _chunk in adapter.read_stream("escape.txt"):
            pass


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_writing_through_an_escaping_link_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter, outside = _link_out_of_root(tmp_path, link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        await adapter.write("escape.txt", b"overwritten", Config())

    assert outside.read_bytes() == b"secret"


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_writing_a_stream_through_an_escaping_link_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter, outside = _link_out_of_root(tmp_path, link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        await adapter.write_stream("escape.txt", _stream(b"over"), Config())

    assert outside.read_bytes() == b"secret"


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_deleting_through_an_escaping_link_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter, outside = _link_out_of_root(tmp_path, link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        await adapter.delete("escape.txt")

    assert outside.exists()


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_moving_an_escaping_link_as_the_source_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter, outside = _link_out_of_root(tmp_path, link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        await adapter.move("escape.txt", "moved.txt", Config())

    assert outside.read_bytes() == b"secret"


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_moving_onto_an_escaping_link_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter, outside = _link_out_of_root(tmp_path, link_handling)
    await adapter.write("real.txt", b"payload", Config())

    with pytest.raises(SymbolicLinkEncounteredError):
        await adapter.move("real.txt", "escape.txt", Config())

    assert outside.read_bytes() == b"secret"


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_copying_an_escaping_link_as_the_source_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter, _outside = _link_out_of_root(tmp_path, link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        await adapter.copy("escape.txt", "copied.txt", Config())


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_copying_onto_an_escaping_link_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter, outside = _link_out_of_root(tmp_path, link_handling)
    await adapter.write("real.txt", b"payload", Config())

    with pytest.raises(SymbolicLinkEncounteredError):
        await adapter.copy("real.txt", "escape.txt", Config())

    assert outside.read_bytes() == b"secret"


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_a_directory_link_on_the_way_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    _ = (outside / "target.txt").write_bytes(b"secret")
    root = tmp_path / "root"
    root.mkdir()
    (root / "linkdir").symlink_to(outside, target_is_directory=True)
    adapter = LocalAdapter(root, link_handling=link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        _ = await adapter.read("linkdir/target.txt")


def _root_behind_a_link(tmp_path: Path) -> Path:
    """Return a link standing for a real directory, as a deployment root often is.

    ``/var`` standing for ``/private/var``, a release directory a deploy
    repoints: the operator names the link and expects the storage to work.
    """
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real, target_is_directory=True)
    return link


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_a_root_that_is_itself_a_link_can_be_written_through(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter = LocalAdapter(_root_behind_a_link(tmp_path), link_handling=link_handling)

    await adapter.write("deep/file.txt", b"payload", Config())

    assert await adapter.read("deep/file.txt") == b"payload"
    assert (tmp_path / "real" / "deep" / "file.txt").read_bytes() == b"payload"


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_a_root_that_is_itself_a_link_accepts_a_created_directory(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    adapter = LocalAdapter(_root_behind_a_link(tmp_path), link_handling=link_handling)

    await adapter.create_directory("made", Config())

    assert (tmp_path / "real" / "made").is_dir()


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_a_link_escaping_a_linked_root_is_still_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    link = _root_behind_a_link(tmp_path)
    outside = tmp_path / "outside.txt"
    _ = outside.write_bytes(b"secret")
    (tmp_path / "real" / "escape.txt").symlink_to(outside)
    adapter = LocalAdapter(link, link_handling=link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        _ = await adapter.read("escape.txt")


@pytest.mark.parametrize("link_handling", list(LinkHandling))
async def test_creating_a_directory_through_an_escaping_link_is_refused(
    tmp_path: Path,
    link_handling: LinkHandling,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root = tmp_path / "root"
    root.mkdir()
    (root / "linkdir").symlink_to(outside, target_is_directory=True)
    adapter = LocalAdapter(root, link_handling=link_handling)

    with pytest.raises(SymbolicLinkEncounteredError):
        await adapter.create_directory("linkdir/made", Config())

    assert not (outside / "made").exists()


async def test_creating_a_directory_through_a_link_inside_the_root_is_refused(
    tmp_path: Path,
) -> None:
    # A link whose target stays inside the root satisfies the prefixer's guard,
    # so what refuses here is the creation walk itself: no component below the
    # root is ever followed, wherever it leads.
    root = tmp_path / "root"
    inside = root / "inside"
    inside.mkdir(parents=True)
    (root / "linkdir").symlink_to(inside, target_is_directory=True)
    adapter = LocalAdapter(root)

    with pytest.raises(UnableToCreateDirectoryError):
        await adapter.create_directory("linkdir/made", Config())

    assert not (inside / "made").exists()


def _walk_through_a_link(tmp_path: Path) -> tuple[str, str]:
    """Plant a link where the creation walk expects a directory, and name the walk."""
    inside = tmp_path / "root" / "inside"
    inside.mkdir(parents=True)
    link = tmp_path / "root" / "linkdir"
    link.symlink_to(inside, target_is_directory=True)

    return (tmp_path / "root").as_posix(), (link / "made").as_posix()


def test_the_creation_walk_closes_each_descriptor_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, location = _walk_through_a_link(tmp_path)
    closed: list[int] = []
    real_close = os.close

    def recording_close(descriptor: int) -> None:
        closed.append(descriptor)
        real_close(descriptor)

    with monkeypatch.context() as patched:
        patched.setattr(os, "close", recording_close)
        with pytest.raises(OSError, match="linkdir"):
            _make_directories(root, location, 0o700)

    assert len(closed) == len(set(closed))


def test_a_link_on_the_creation_walk_surfaces_its_own_error(tmp_path: Path) -> None:
    root, location = _walk_through_a_link(tmp_path)

    with pytest.raises(OSError, match="linkdir") as caught:
        _make_directories(root, location, 0o700)

    # Two kernels, two words for the same refusal: Linux reports the link it was
    # told not to follow, Darwin reports that a link is not the directory asked
    # for. Either is the walk's own answer; a closed descriptor's EBADF is not.
    assert caught.value.errno in (errno.ELOOP, errno.ENOTDIR)
