from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest
from fsspec.implementations.memory import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information
    MemoryFileSystem,
)

from tests.support.scripted_adapter import ScriptedAdapter, TemporaryUrlScriptedAdapter
from xtr_storage.adapter.generic_fsspec_adapter import GenericFsspecAdapter
from xtr_storage.adapter.in_memory_adapter import InMemoryAdapter
from xtr_storage.config import Config
from xtr_storage.exception import (
    FeatureNotSupportedError,
    UnableToCopyFileError,
    UnableToDeleteFileError,
    UnableToMoveFileError,
    UnableToReadFileError,
    UnableToResolveMountError,
    UnableToRetrieveMetadataError,
)
from xtr_storage.mount_manager import MountManager
from xtr_storage.storage import Storage
from xtr_storage.storage_operator_interface import StorageOperatorInterface
from xtr_storage.visibility import Visibility

pytestmark = pytest.mark.anyio

_FOOBAR_MD5 = "3858f62230ac3c915f300c664312c63f"


def memory_storage(default_visibility: Visibility = Visibility.PUBLIC) -> Storage:
    """A storage whose files, and their visibility, live in a store of its own."""
    return Storage(InMemoryAdapter(default_visibility))


def mounted(storage: object) -> StorageOperatorInterface:
    """Present a stand-in as something mountable, which is all a mount asks of it."""
    return cast("StorageOperatorInterface", storage)


def storage_without_visibility() -> Storage:
    """A storage over a filesystem from outside, which therefore has no visibility."""
    filesystem = MemoryFileSystem(skip_instance_cache=True)
    filesystem.store = {}
    filesystem.pseudo_dirs = [""]

    return Storage(GenericFsspecAdapter(filesystem))


class ClosingStorage:
    """A mounted thing that only closes — and can be told to refuse."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error: Exception | None = error
        self.closed: bool = False

    async def close(self) -> None:
        self.closed = True
        if self.error is not None:
            raise self.error


class UnclosableStorage:
    """A mounted thing holding nothing open, and so having no close to call."""


def test_a_mount_manager_satisfies_the_operator_interface() -> None:
    operator: StorageOperatorInterface = MountManager({})

    assert isinstance(operator, StorageOperatorInterface)


# --- routing ----------------------------------------------------------------


async def test_reading_reaches_the_storage_its_location_names() -> None:
    manager = MountManager(
        {
            "uploads": Storage(ScriptedAdapter(files={"a.txt": b"one"})),
            "archive": Storage(ScriptedAdapter(files={"a.txt": b"two"})),
        },
    )

    assert await manager.read("archive://a.txt") == b"two"


async def test_reading_a_stream_reaches_the_storage_its_location_names() -> None:
    manager = MountManager({"uploads": Storage(ScriptedAdapter(files={"a.txt": b"one"}))})

    chunks = [chunk async for chunk in manager.read_stream("uploads://a.txt")]

    assert b"".join(chunks) == b"one"


async def test_writing_reaches_the_storage_its_location_names() -> None:
    uploads = ScriptedAdapter()
    archive = ScriptedAdapter()
    manager = MountManager({"uploads": Storage(uploads), "archive": Storage(archive)})

    await manager.write("uploads://a/b.txt", b"x")

    assert uploads.files == {"a/b.txt": b"x"}
    assert archive.files == {}


async def test_streaming_a_write_reaches_the_storage_its_location_names() -> None:
    adapter = ScriptedAdapter()
    manager = MountManager({"uploads": Storage(adapter)})

    await manager.write_stream("uploads://a.txt", [b"one", b"two"])

    assert adapter.files == {"a.txt": b"onetwo"}


async def test_existence_checks_reach_the_storage_their_location_names() -> None:
    manager = MountManager(
        {
            "uploads": Storage(ScriptedAdapter(files={"a/b.txt": b"x"})),
            "archive": Storage(ScriptedAdapter()),
        },
    )

    assert await manager.file_exists("uploads://a/b.txt")
    assert await manager.directory_exists("uploads://a")
    assert await manager.has("uploads://a/b.txt")
    assert not await manager.file_exists("archive://a/b.txt")


async def test_metadata_reaches_the_storage_its_path_names() -> None:
    manager = MountManager({"uploads": memory_storage()})
    await manager.write("uploads://a.txt", b"hello")

    assert await manager.file_size("uploads://a.txt") == 5
    assert await manager.mime_type("uploads://a.txt") == "text/plain"
    assert await manager.last_modified("uploads://a.txt") > 0


async def test_visibility_reaches_the_storage_its_path_names() -> None:
    manager = MountManager({"uploads": memory_storage()})
    await manager.write("uploads://a.txt", b"x", {Config.VISIBILITY: Visibility.PRIVATE})

    assert await manager.visibility("uploads://a.txt") is Visibility.PRIVATE


async def test_setting_visibility_reaches_the_storage_its_path_names() -> None:
    adapter = ScriptedAdapter(files={"a.txt": b"x"})
    manager = MountManager({"uploads": Storage(adapter)})

    await manager.set_visibility("uploads://a.txt", Visibility.PRIVATE)

    assert adapter.visibilities == {"a.txt": Visibility.PRIVATE}


async def test_deleting_reaches_the_storage_its_location_names() -> None:
    adapter = ScriptedAdapter(files={"a.txt": b"x"})
    manager = MountManager({"uploads": Storage(adapter)})

    await manager.delete("uploads://a.txt")

    assert adapter.files == {}


async def test_deleting_a_directory_reaches_the_storage_its_location_names() -> None:
    adapter = ScriptedAdapter(files={"a/b.txt": b"x"})
    manager = MountManager({"uploads": Storage(adapter)})

    await manager.delete_directory("uploads://a")

    assert adapter.files == {}


async def test_creating_a_directory_reaches_the_storage_its_location_names() -> None:
    adapter = ScriptedAdapter()
    manager = MountManager({"uploads": Storage(adapter)})

    await manager.create_directory("uploads://a")

    assert adapter.directories == {"a"}


# --- locations that route nowhere -------------------------------------------


async def test_a_location_carrying_no_mount_name_is_refused() -> None:
    manager = MountManager({"uploads": memory_storage()})

    with pytest.raises(UnableToResolveMountError) as raised:
        _ = await manager.read("a.txt")

    assert raised.value.location == "a.txt"


async def test_a_location_carrying_an_empty_mount_name_is_refused() -> None:
    manager = MountManager({"uploads": memory_storage()})

    with pytest.raises(UnableToResolveMountError, match="empty"):
        _ = await manager.read("://a.txt")


async def test_a_location_naming_no_mounted_storage_is_refused() -> None:
    manager = MountManager({"uploads": memory_storage()})

    with pytest.raises(UnableToResolveMountError, match="archive"):
        _ = await manager.read("archive://a.txt")


def test_a_listing_of_a_location_routing_nowhere_is_refused_where_it_is_asked_for() -> None:
    manager = MountManager({"uploads": memory_storage()})

    with pytest.raises(UnableToResolveMountError):
        _ = manager.list_contents()


# --- listings ---------------------------------------------------------------


async def test_a_listing_names_every_entry_at_its_full_location() -> None:
    manager = MountManager({"uploads": memory_storage()})
    await manager.write("uploads://a/b.txt", b"x")
    await manager.write("uploads://a/c.txt", b"y")

    paths = sorted([entry.path async for entry in manager.list_contents("uploads://a")])

    assert paths == ["uploads://a/b.txt", "uploads://a/c.txt"]


async def test_a_deep_listing_names_its_directories_at_their_full_location_too() -> None:
    manager = MountManager({"uploads": memory_storage()})
    await manager.write("uploads://a/b/c.txt", b"x")

    entries = [entry async for entry in manager.list_contents("uploads://", deep=True)]

    assert "uploads://a/b/c.txt" in [entry.path for entry in entries]
    assert all(entry.path.startswith("uploads://") for entry in entries)
    assert any(entry.is_dir for entry in entries)


# --- copying and moving within one storage ----------------------------------


async def test_a_copy_within_one_storage_delegates_to_that_storage() -> None:
    adapter = ScriptedAdapter(files={"a.txt": b"x"})
    storage = Storage(adapter)
    manager = MountManager({"uploads": storage, "mirror": storage})

    await manager.copy("uploads://a.txt", "mirror://b.txt")

    assert "copy a.txt->b.txt" in adapter.calls


async def test_a_move_within_one_storage_delegates_to_that_storage() -> None:
    adapter = ScriptedAdapter(files={"a.txt": b"x"})
    storage = Storage(adapter)
    manager = MountManager({"uploads": storage, "mirror": storage})

    await manager.move("uploads://a.txt", "mirror://b.txt")

    assert "move a.txt->b.txt" in adapter.calls
    assert adapter.files == {"b.txt": b"x"}


# --- copying across storages ------------------------------------------------


async def test_a_copy_across_storages_carries_the_bytes_over() -> None:
    manager = MountManager({"uploads": memory_storage(), "archive": memory_storage()})
    await manager.write("uploads://a.txt", b"x")

    await manager.copy("uploads://a.txt", "archive://b.txt")

    assert await manager.read("archive://b.txt") == b"x"
    assert await manager.read("uploads://a.txt") == b"x"


async def test_a_copy_across_storages_carries_the_visibility_over() -> None:
    manager = MountManager({"uploads": memory_storage(), "archive": memory_storage()})
    await manager.write("uploads://a.txt", b"x", {Config.VISIBILITY: Visibility.PRIVATE})

    await manager.copy("uploads://a.txt", "archive://b.txt")

    assert await manager.visibility("archive://b.txt") is Visibility.PRIVATE


async def test_a_copy_uses_the_visibility_the_call_names() -> None:
    manager = MountManager({"uploads": memory_storage(), "archive": memory_storage()})
    await manager.write("uploads://a.txt", b"x")

    await manager.copy(
        "uploads://a.txt",
        "archive://b.txt",
        {Config.VISIBILITY: Visibility.PRIVATE},
    )

    assert await manager.visibility("archive://b.txt") is Visibility.PRIVATE


async def test_a_copy_asked_to_keep_no_visibility_leaves_the_destination_its_own() -> None:
    manager = MountManager(
        {"uploads": memory_storage(), "archive": memory_storage(Visibility.PRIVATE)},
    )
    await manager.write("uploads://a.txt", b"x")

    await manager.copy("uploads://a.txt", "archive://b.txt", {Config.RETAIN_VISIBILITY: False})

    assert await manager.visibility("archive://b.txt") is Visibility.PRIVATE


async def test_a_copy_from_a_storage_without_visibility_carries_none() -> None:
    manager = MountManager(
        {"plain": storage_without_visibility(), "archive": memory_storage(Visibility.PRIVATE)},
    )
    await manager.write("plain://a.txt", b"x")

    await manager.copy("plain://a.txt", "archive://b.txt")

    assert await manager.read("archive://b.txt") == b"x"
    assert await manager.visibility("archive://b.txt") is Visibility.PRIVATE


async def test_a_copy_into_a_storage_without_visibility_still_arrives() -> None:
    manager = MountManager({"uploads": memory_storage(), "plain": storage_without_visibility()})
    await manager.write("uploads://a.txt", b"x", {Config.VISIBILITY: Visibility.PRIVATE})

    await manager.copy("uploads://a.txt", "plain://b.txt")

    assert await manager.read("plain://b.txt") == b"x"
    with pytest.raises(FeatureNotSupportedError):
        _ = await manager.visibility("plain://b.txt")


async def test_a_copy_whose_read_fails_is_a_copy_failure() -> None:
    source = ScriptedAdapter(
        files={"a.txt": b"x"},
        fail_on={"read_stream": UnableToReadFileError("a.txt", "the backend refused")},
    )
    manager = MountManager({"uploads": Storage(source), "archive": memory_storage()})

    with pytest.raises(UnableToCopyFileError) as raised:
        await manager.copy("uploads://a.txt", "archive://b.txt")

    assert raised.value.source == "uploads://a.txt"
    assert raised.value.destination == "archive://b.txt"
    assert isinstance(raised.value.__cause__, UnableToReadFileError)


async def test_a_copy_whose_visibility_lookup_fails_is_a_copy_failure() -> None:
    source = ScriptedAdapter(
        files={"a.txt": b"x"},
        fail_on={"visibility": UnableToRetrieveMetadataError.visibility("a.txt")},
    )
    manager = MountManager({"uploads": Storage(source), "archive": memory_storage()})

    with pytest.raises(UnableToCopyFileError) as raised:
        await manager.copy("uploads://a.txt", "archive://b.txt")

    assert isinstance(raised.value.__cause__, UnableToRetrieveMetadataError)


# --- moving across storages -------------------------------------------------


async def test_a_move_across_storages_leaves_nothing_at_the_source() -> None:
    manager = MountManager({"uploads": memory_storage(), "archive": memory_storage()})
    await manager.write("uploads://a.txt", b"x")

    await manager.move("uploads://a.txt", "archive://b.txt")

    assert await manager.read("archive://b.txt") == b"x"
    assert not await manager.file_exists("uploads://a.txt")


async def test_a_move_whose_source_cannot_be_deleted_leaves_it_in_place() -> None:
    source = ScriptedAdapter(
        files={"a.txt": b"x"},
        fail_on={"delete": UnableToDeleteFileError("a.txt", "the backend refused")},
    )
    manager = MountManager({"uploads": Storage(source), "archive": memory_storage()})

    with pytest.raises(UnableToMoveFileError) as raised:
        await manager.move("uploads://a.txt", "archive://b.txt")

    assert raised.value.source == "uploads://a.txt"
    assert raised.value.destination == "archive://b.txt"
    assert source.files == {"a.txt": b"x"}
    assert await manager.read("archive://b.txt") == b"x"


async def test_a_move_whose_copy_fails_is_a_move_failure() -> None:
    source = ScriptedAdapter(
        files={"a.txt": b"x"},
        fail_on={"read_stream": UnableToReadFileError("a.txt", "the backend refused")},
    )
    manager = MountManager({"uploads": Storage(source), "archive": memory_storage()})

    with pytest.raises(UnableToMoveFileError):
        await manager.move("uploads://a.txt", "archive://b.txt")

    assert source.files == {"a.txt": b"x"}


# --- addresses and digests --------------------------------------------------


async def test_a_public_url_comes_from_the_storage_that_holds_the_file() -> None:
    manager = MountManager(
        {
            "cdn": Storage(
                ScriptedAdapter(files={"a.txt": b"x"}),
                {Config.PUBLIC_URL: "https://cdn.example/"},
            ),
        },
    )

    assert await manager.public_url("cdn://a.txt") == "https://cdn.example/a.txt"


async def test_a_temporary_url_comes_from_the_storage_that_holds_the_file() -> None:
    manager = MountManager(
        {"uploads": Storage(TemporaryUrlScriptedAdapter(files={"a.txt": b"x"}))},
    )
    expires_at = datetime(2030, 1, 1, tzinfo=UTC)

    url = await manager.temporary_url("uploads://a.txt", expires_at)

    assert url == f"https://backend.example/a.txt?expires={int(expires_at.timestamp())}"


async def test_a_checksum_comes_from_the_storage_that_holds_the_file() -> None:
    manager = MountManager({"uploads": Storage(ScriptedAdapter(files={"a.txt": b"foobar"}))})

    assert await manager.checksum("uploads://a.txt") == _FOOBAR_MD5


# --- standing options -------------------------------------------------------


async def test_the_standing_options_reach_a_call_that_names_none() -> None:
    adapter = ScriptedAdapter()
    manager = MountManager({"uploads": Storage(adapter)}, {Config.VISIBILITY: Visibility.PRIVATE})

    await manager.write("uploads://a.txt", b"x")

    assert adapter.visibilities == {"a.txt": Visibility.PRIVATE}


async def test_the_options_of_a_call_win_over_the_standing_ones() -> None:
    adapter = ScriptedAdapter()
    manager = MountManager({"uploads": Storage(adapter)}, {Config.VISIBILITY: Visibility.PRIVATE})

    await manager.write("uploads://a.txt", b"x", {Config.VISIBILITY: Visibility.PUBLIC})

    assert adapter.visibilities == {"a.txt": Visibility.PUBLIC}


async def test_a_standing_visibility_does_not_override_what_a_copy_keeps() -> None:
    manager = MountManager(
        {"uploads": memory_storage(), "archive": memory_storage()},
        {Config.VISIBILITY: Visibility.PUBLIC},
    )
    await manager.write("uploads://a.txt", b"x", {Config.VISIBILITY: Visibility.PRIVATE})

    await manager.copy("uploads://a.txt", "archive://b.txt")

    assert await manager.visibility("archive://b.txt") is Visibility.PRIVATE


# --- closing ----------------------------------------------------------------


async def test_closing_closes_every_mounted_storage() -> None:
    uploads = ScriptedAdapter()
    archive = ScriptedAdapter()
    manager = MountManager({"uploads": Storage(uploads), "archive": Storage(archive)})

    await manager.close()

    assert uploads.closed
    assert archive.closed


async def test_a_storage_that_will_not_close_does_not_stop_the_rest() -> None:
    refusing = ClosingStorage(RuntimeError("the client is stuck"))
    following = ClosingStorage()
    manager = MountManager({"refusing": mounted(refusing), "following": mounted(following)})

    with pytest.raises(RuntimeError, match="stuck"):
        await manager.close()

    assert following.closed


async def test_a_storage_with_nothing_to_close_is_passed_over() -> None:
    adapter = ScriptedAdapter()
    manager = MountManager({"plain": mounted(UnclosableStorage()), "uploads": Storage(adapter)})

    await manager.close()

    assert adapter.closed


async def test_leaving_the_context_closes_every_mounted_storage() -> None:
    adapter = ScriptedAdapter()

    async with MountManager({"uploads": Storage(adapter)}) as manager:
        await manager.write("uploads://a.txt", b"x")

    assert adapter.closed
