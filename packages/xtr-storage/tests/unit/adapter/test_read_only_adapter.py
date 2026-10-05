"""The read-only adapter refuses every change and passes every read on.

Two halves to prove. That each way of changing something fails with the failure
of that very operation, and fails here — the wrapped adapter is never asked, so
a backend whose credentials would have allowed the write never hears about it.
And that everything else, reads and the three capabilities alike, reaches the
adapter underneath unchanged, including what it answers when it has no such
capability to offer.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, TypeAlias

import pytest

from tests.support.scripted_adapter import (
    ChecksumScriptedAdapter,
    PublicUrlScriptedAdapter,
    ScriptedAdapter,
    TemporaryUrlScriptedAdapter,
)
from xtr_storage.adapter.read_only_adapter import ReadOnlyAdapter
from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    StorageOperationFailedError,
    UnableToCopyFileError,
    UnableToCreateDirectoryError,
    UnableToDeleteDirectoryError,
    UnableToDeleteFileError,
    UnableToGeneratePublicUrlError,
    UnableToGenerateTemporaryUrlError,
    UnableToMoveFileError,
    UnableToSetVisibilityError,
    UnableToWriteFileError,
)
from xtr_storage.storage import Storage
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio

_REFUSED = "this storage is read-only"
_EXPIRES_AT = datetime(2030, 1, 1, tzinfo=UTC)
_FOOBAR_MD5 = "3858f62230ac3c915f300c664312c63f"

_Change: TypeAlias = Callable[[ReadOnlyAdapter], Awaitable[None]]


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    """Yield the given chunks, as the async source a streamed write takes."""
    for chunk in chunks:
        yield chunk


_CHANGES: list[tuple[type[StorageOperationFailedError], _Change]] = [
    (UnableToWriteFileError, lambda adapter: adapter.write("f.txt", b"x", Config())),
    (
        UnableToWriteFileError,
        lambda adapter: adapter.write_stream("f.txt", _stream(b"x"), Config()),
    ),
    (UnableToDeleteFileError, lambda adapter: adapter.delete("f.txt")),
    (UnableToDeleteDirectoryError, lambda adapter: adapter.delete_directory("d")),
    (UnableToCreateDirectoryError, lambda adapter: adapter.create_directory("d", Config())),
    (
        UnableToSetVisibilityError,
        lambda adapter: adapter.set_visibility("f.txt", Visibility.PUBLIC),
    ),
    (UnableToMoveFileError, lambda adapter: adapter.move("f.txt", "g.txt", Config())),
    (UnableToCopyFileError, lambda adapter: adapter.copy("f.txt", "g.txt", Config())),
]


@pytest.mark.parametrize(
    ("expected", "change"),
    _CHANGES,
    ids=[
        "write",
        "write_stream",
        "delete",
        "delete_directory",
        "create_directory",
        "set_visibility",
        "move",
        "copy",
    ],
)
async def test_every_change_fails_as_its_own_operation(
    expected: type[StorageOperationFailedError],
    change: _Change,
) -> None:
    inner = ScriptedAdapter(files={"f.txt": b"x"})
    adapter = ReadOnlyAdapter(inner)

    with pytest.raises(expected) as raised:
        await change(adapter)

    assert _REFUSED in str(raised.value)
    assert inner.calls == []


async def test_a_refused_change_leaves_the_files_alone() -> None:
    inner = ScriptedAdapter(files={"f.txt": b"first"})
    adapter = ReadOnlyAdapter(inner)

    with pytest.raises(UnableToWriteFileError):
        await adapter.write("f.txt", b"second", Config())

    assert inner.files == {"f.txt": b"first"}


async def test_it_reads_a_file_from_the_wrapped_adapter() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"hello"}))

    assert await adapter.read("a.txt") == b"hello"


async def test_it_streams_a_file_from_the_wrapped_adapter() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"hello"}))

    chunks = [chunk async for chunk in adapter.read_stream("a.txt")]

    assert b"".join(chunks) == b"hello"


async def test_it_answers_whether_a_file_is_there_from_the_wrapped_adapter() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"hello"}))

    assert await adapter.file_exists("a.txt")
    assert not await adapter.file_exists("b.txt")


async def test_it_answers_whether_a_directory_is_there_from_the_wrapped_adapter() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"d/a.txt": b"hello"}))

    assert await adapter.directory_exists("d")
    assert not await adapter.directory_exists("e")


async def test_it_reports_a_files_size_from_the_wrapped_adapter() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"12345"}))

    assert (await adapter.file_size("a.txt")).file_size == 5


async def test_it_reports_what_a_file_holds_from_the_wrapped_adapter() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"x"}))

    assert (await adapter.mime_type("a.txt")).mime_type == "text/plain"


async def test_it_reports_when_a_file_last_changed_from_the_wrapped_adapter() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"x"}))

    assert (await adapter.last_modified("a.txt")).last_modified == 1_700_000_000


async def test_it_reports_who_may_read_a_file_from_the_wrapped_adapter() -> None:
    inner = ScriptedAdapter(files={"a.txt": b"x"}, visibility={"a.txt": Visibility.PRIVATE})
    adapter = ReadOnlyAdapter(inner)

    assert (await adapter.visibility("a.txt")).visibility == Visibility.PRIVATE


async def test_it_lists_what_the_wrapped_adapter_holds() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"x", "d/b.txt": b"y"}))

    paths = [entry.path async for entry in adapter.list_contents("", deep=True)]

    assert paths == ["a.txt", "d/b.txt"]


async def test_it_answers_to_every_capability_a_storage_looks_for() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter())

    assert isinstance(adapter, StorageAdapterInterface)
    assert isinstance(adapter, ChecksumProviderInterface)
    assert isinstance(adapter, PublicUrlGeneratorInterface)
    assert isinstance(adapter, TemporaryUrlGeneratorInterface)


async def test_it_hands_back_the_wrapped_adapters_checksum() -> None:
    inner = ChecksumScriptedAdapter(
        checksum_value="from-the-backend",
        supported_algorithms=("md5",),
        files={"a.txt": b"x"},
    )
    adapter = ReadOnlyAdapter(inner)

    assert await adapter.checksum("a.txt", Config()) == "from-the-backend"


@pytest.mark.parametrize(
    ("config", "expected_algorithm"),
    [
        (Config(), "md5"),
        (Config({Config.CHECKSUM_ALGORITHM: "sha256"}), "sha256"),
    ],
    ids=["default", "named"],
)
async def test_a_checksum_asks_for_the_fallback_when_the_wrapped_adapter_keeps_none(
    config: Config,
    expected_algorithm: str,
) -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"x"}))

    with pytest.raises(ChecksumAlgorithmNotSupportedError) as raised:
        _ = await adapter.checksum("a.txt", config)

    assert raised.value.location == "a.txt"
    assert raised.value.algorithm == expected_algorithm


async def test_a_storage_over_it_digests_the_bytes_when_no_digest_is_kept() -> None:
    storage = Storage(ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"foobar"})))

    assert await storage.checksum("a.txt") == _FOOBAR_MD5


async def test_a_storage_over_it_refuses_a_delete() -> None:
    inner = ScriptedAdapter(files={"a.txt": b"x"})
    storage = Storage(ReadOnlyAdapter(inner))

    with pytest.raises(UnableToDeleteFileError):
        await storage.delete("a.txt")

    assert inner.files == {"a.txt": b"x"}


async def test_it_hands_back_the_wrapped_adapters_public_url() -> None:
    adapter = ReadOnlyAdapter(PublicUrlScriptedAdapter(files={"a.txt": b"x"}))

    assert await adapter.public_url("a.txt", Config()) == "https://backend.example/a.txt"


async def test_a_public_url_is_refused_when_the_wrapped_adapter_has_none() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"x"}))

    with pytest.raises(UnableToGeneratePublicUrlError) as raised:
        _ = await adapter.public_url("a.txt", Config())

    assert raised.value.location == "a.txt"
    assert "wrapped adapter" in raised.value.reason


async def test_it_hands_back_the_wrapped_adapters_temporary_url() -> None:
    adapter = ReadOnlyAdapter(TemporaryUrlScriptedAdapter(files={"a.txt": b"x"}))

    url = await adapter.temporary_url("a.txt", _EXPIRES_AT, Config())

    assert url == f"https://backend.example/a.txt?expires={int(_EXPIRES_AT.timestamp())}"


async def test_a_temporary_url_is_refused_when_the_wrapped_adapter_signs_none() -> None:
    adapter = ReadOnlyAdapter(ScriptedAdapter(files={"a.txt": b"x"}))

    with pytest.raises(UnableToGenerateTemporaryUrlError) as raised:
        _ = await adapter.temporary_url("a.txt", _EXPIRES_AT, Config())

    assert raised.value.location == "a.txt"
    assert "wrapped adapter" in raised.value.reason


async def test_closing_closes_the_wrapped_adapter() -> None:
    inner = ScriptedAdapter()
    adapter = ReadOnlyAdapter(inner)

    await adapter.close()

    assert inner.closed
