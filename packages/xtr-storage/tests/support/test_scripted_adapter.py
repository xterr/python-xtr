from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.scripted_adapter import (
    ChecksumScriptedAdapter,
    PublicUrlScriptedAdapter,
    ScriptedAdapter,
    TemporaryUrlScriptedAdapter,
)
from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.exception import ChecksumAlgorithmNotSupportedError, UnableToReadFileError
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


async def _drain(iterator: AsyncIterator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in iterator])


def test_the_fake_satisfies_the_adapter_interface() -> None:
    assert isinstance(ScriptedAdapter(), StorageAdapterInterface)


def test_the_base_fake_advertises_no_capabilities() -> None:
    adapter = ScriptedAdapter()

    assert not isinstance(adapter, ChecksumProviderInterface)
    assert not isinstance(adapter, PublicUrlGeneratorInterface)
    assert not isinstance(adapter, TemporaryUrlGeneratorInterface)


def test_the_capability_subclasses_advertise_their_capability() -> None:
    assert isinstance(ChecksumScriptedAdapter(), ChecksumProviderInterface)
    assert isinstance(PublicUrlScriptedAdapter(), PublicUrlGeneratorInterface)
    assert isinstance(TemporaryUrlScriptedAdapter(), TemporaryUrlGeneratorInterface)


async def test_a_write_round_trips_and_is_recorded() -> None:
    adapter = ScriptedAdapter()

    await adapter.write("a.txt", b"hello", Config())

    assert await adapter.read("a.txt") == b"hello"
    assert "write a.txt" in adapter.calls
    assert adapter.received_paths[0] == "a.txt"


async def test_a_stream_write_joins_its_chunks() -> None:
    adapter = ScriptedAdapter()

    async def chunks() -> AsyncIterator[bytes]:
        yield b"foo"
        yield b"bar"

    await adapter.write_stream("a.txt", chunks(), Config())

    assert adapter.files["a.txt"] == b"foobar"


async def test_reading_a_missing_file_raises() -> None:
    adapter = ScriptedAdapter()

    with pytest.raises(UnableToReadFileError):
        _ = await adapter.read("missing.txt")


async def test_deleting_a_missing_file_is_silent() -> None:
    adapter = ScriptedAdapter()

    await adapter.delete("missing.txt")

    assert "delete missing.txt" in adapter.calls


async def test_an_armed_method_raises_the_exact_exception() -> None:
    boom = RuntimeError("scripted failure")
    adapter = ScriptedAdapter(fail_on={"write": boom})

    with pytest.raises(RuntimeError) as caught:
        await adapter.write("a.txt", b"x", Config())

    assert caught.value is boom


async def test_visibility_follows_a_copy() -> None:
    adapter = ScriptedAdapter(
        files={"a.txt": b"x"},
        visibility={"a.txt": Visibility.PRIVATE},
    )

    await adapter.copy("a.txt", "b.txt", Config())

    attributes = await adapter.visibility("b.txt")
    assert attributes.visibility is Visibility.PRIVATE


async def test_listing_yields_the_files_under_a_path() -> None:
    adapter = ScriptedAdapter(files={"dir/a.txt": b"1", "dir/b.txt": b"2", "other.txt": b"3"})

    paths = [entry.path async for entry in adapter.list_contents("dir", deep=False)]

    assert paths == ["dir/a.txt", "dir/b.txt"]


async def test_a_provider_answers_a_supported_algorithm() -> None:
    adapter = ChecksumScriptedAdapter(checksum_value="etag-value", supported_algorithms=("etag",))
    config = Config({Config.CHECKSUM_ALGORITHM: "etag"})

    assert await adapter.checksum("a.txt", config) == "etag-value"


async def test_a_provider_refuses_an_algorithm_it_does_not_keep() -> None:
    adapter = ChecksumScriptedAdapter(supported_algorithms=("etag",))
    config = Config({Config.CHECKSUM_ALGORITHM: "md5"})

    with pytest.raises(ChecksumAlgorithmNotSupportedError):
        _ = await adapter.checksum("a.txt", config)


async def test_a_read_stream_yields_the_stored_bytes() -> None:
    adapter = ScriptedAdapter(files={"a.txt": b"streamed"})

    assert await _drain(adapter.read_stream("a.txt")) == b"streamed"


async def test_close_marks_the_adapter_closed() -> None:
    adapter = ScriptedAdapter()

    await adapter.close()

    assert adapter.closed
