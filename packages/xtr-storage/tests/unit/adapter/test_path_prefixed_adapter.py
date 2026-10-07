"""The path-prefixed adapter translates paths down and everything else back up.

Three things to pin. Paths reach the wrapped adapter with the prefix on, which is
what makes the prefix the only place it is written down. Listings and metadata
come back in the caller's terms, so an answer can be handed straight back to the
same storage. And a failure about a prefixed path is told again about the path
the caller used, keeping the original as its cause — with anything this library
does not recognise left exactly as it was raised rather than guessed at.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar, TypeAlias

import pytest
from typing_extensions import override

from tests.support.scripted_adapter import (
    ChecksumScriptedAdapter,
    PublicUrlScriptedAdapter,
    ScriptedAdapter,
    TemporaryUrlScriptedAdapter,
)
from xtr_storage.adapter.path_prefixed_adapter import PathPrefixedAdapter
from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface
from xtr_storage.checksum_provider_interface import ChecksumProviderInterface
from xtr_storage.config import Config
from xtr_storage.directory_attributes import DirectoryAttributes
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    FeatureNotSupportedError,
    InvalidArgumentError,
    PathTraversalDetectedError,
    StorageOperationFailedError,
    UnableToCheckDirectoryExistenceError,
    UnableToCheckFileExistenceError,
    UnableToCreateDirectoryError,
    UnableToDeleteDirectoryError,
    UnableToDeleteFileError,
    UnableToGeneratePublicUrlError,
    UnableToGenerateTemporaryUrlError,
    UnableToListContentsError,
    UnableToMoveFileError,
    UnableToReadFileError,
    UnableToRetrieveMetadataError,
    UnableToSetVisibilityError,
    UnableToWriteFileError,
)
from xtr_storage.feature import Feature
from xtr_storage.file_attributes import FileAttributes
from xtr_storage.operation import Operation
from xtr_storage.storage import Storage
from xtr_storage.url_generation.public_url_generator_interface import PublicUrlGeneratorInterface
from xtr_storage.url_generation.temporary_url_generator_interface import (
    TemporaryUrlGeneratorInterface,
)
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_storage.storage_attributes import StorageAttributes

pytestmark = pytest.mark.anyio

_PREFIX = "some/prefix"
_PATH = "a.txt"
_INNER_PATH = "some/prefix/a.txt"
_EXPIRES_AT = datetime(2030, 1, 1, tzinfo=UTC)

_Call: TypeAlias = Callable[[PathPrefixedAdapter], Awaitable[object]]
_MetadataRead: TypeAlias = Callable[[PathPrefixedAdapter], Awaitable[FileAttributes]]


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    """Yield the given chunks, as the async source a streamed write takes."""
    for chunk in chunks:
        yield chunk


async def _drain_stream(adapter: PathPrefixedAdapter) -> None:
    """Pull a streamed read to its end, where a failure mid-read surfaces."""
    async for _chunk in adapter.read_stream(_PATH):
        pass


async def _drain_listing(adapter: PathPrefixedAdapter) -> None:
    """Pull a listing to its end, where a failure mid-listing surfaces."""
    async for _entry in adapter.list_contents(_PATH, deep=True):
        pass


class _MixedListingAdapter(ScriptedAdapter):
    """Lists a directory beside a file, which the dictionary-backed fake never does."""

    @override
    async def list_contents(self, path: str, deep: bool) -> AsyncIterator[StorageAttributes]:
        del deep
        self._record("list_contents", path)

        yield DirectoryAttributes(path=f"{path}/sub")
        yield FileAttributes(path=f"{path}/a.txt")


class _OddShapeError(StorageOperationFailedError):
    """A failure of a shape this library does not define, so nothing can rebuild it."""

    operation: ClassVar[Operation] = Operation.READ

    def __init__(self, detail: str) -> None:
        super().__init__(detail)


@pytest.mark.parametrize("prefix", ["", "/", "//", "\\", "/\\"])
async def test_a_prefix_that_names_no_path_is_refused(prefix: str) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = PathPrefixedAdapter(ScriptedAdapter(), prefix)


@pytest.mark.parametrize("prefix", ["..", "../escape", "a/../..", "a/../../b"])
async def test_a_prefix_that_climbs_above_the_root_is_refused(prefix: str) -> None:
    with pytest.raises(PathTraversalDetectedError):
        _ = PathPrefixedAdapter(ScriptedAdapter(), prefix)


async def test_a_prefix_is_normalised_before_it_roots_the_storage() -> None:
    inner = ScriptedAdapter()
    adapter = PathPrefixedAdapter(inner, "some//prefix/./")

    await adapter.write(_PATH, b"payload", Config())

    assert inner.files == {_INNER_PATH: b"payload"}


async def test_a_write_lands_under_the_prefix() -> None:
    inner = ScriptedAdapter()
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    await adapter.write(_PATH, b"payload", Config())

    assert inner.files == {_INNER_PATH: b"payload"}


async def test_a_streamed_write_lands_under_the_prefix() -> None:
    inner = ScriptedAdapter()
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    await adapter.write_stream(_PATH, _stream(b"foo", b"bar"), Config())

    assert inner.files == {_INNER_PATH: b"foobar"}


async def test_it_reads_back_what_it_wrote() -> None:
    adapter = PathPrefixedAdapter(ScriptedAdapter(), _PREFIX)
    await adapter.write(_PATH, b"payload", Config())

    assert await adapter.read(_PATH) == b"payload"


async def test_a_streamed_read_reaches_the_prefixed_path() -> None:
    inner = ScriptedAdapter(files={_INNER_PATH: b"payload"})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    chunks = [chunk async for chunk in adapter.read_stream(_PATH)]

    assert b"".join(chunks) == b"payload"
    assert inner.received_paths == [_INNER_PATH]


@pytest.mark.parametrize(
    ("caller_path", "inner_path"),
    [
        (_PATH, _INNER_PATH),
        ("", _PREFIX),
        ("/a.txt", _INNER_PATH),
        ("d/b.txt", "some/prefix/d/b.txt"),
    ],
    ids=["file", "the root itself", "a leading separator", "nested"],
)
async def test_a_path_reaches_the_wrapped_adapter_under_the_prefix(
    caller_path: str,
    inner_path: str,
) -> None:
    inner = ScriptedAdapter()
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    _ = await adapter.file_exists(caller_path)

    assert inner.received_paths == [inner_path]


async def test_a_listing_drops_the_prefix() -> None:
    inner = ScriptedAdapter(files={_INNER_PATH: b"x", "some/prefix/d/b.txt": b"y"})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    paths = [entry.path async for entry in adapter.list_contents("", deep=True)]

    assert paths == ["a.txt", "d/b.txt"]


async def test_a_listing_keeps_a_directory_a_directory() -> None:
    adapter = PathPrefixedAdapter(_MixedListingAdapter(), _PREFIX)

    entries = [entry async for entry in adapter.list_contents("", deep=False)]

    assert [(entry.path, entry.type) for entry in entries] == [("sub", "dir"), ("a.txt", "file")]


_METADATA_READS: list[_MetadataRead] = [
    lambda adapter: adapter.file_size(_PATH),
    lambda adapter: adapter.last_modified(_PATH),
    lambda adapter: adapter.mime_type(_PATH),
    lambda adapter: adapter.visibility(_PATH),
]


@pytest.mark.parametrize(
    "read_metadata",
    _METADATA_READS,
    ids=["file_size", "last_modified", "mime_type", "visibility"],
)
async def test_metadata_comes_back_at_the_path_the_caller_used(
    read_metadata: _MetadataRead,
) -> None:
    inner = ScriptedAdapter(files={_INNER_PATH: b"payload"})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    attributes = await read_metadata(adapter)

    assert attributes.path == _PATH
    assert inner.received_paths == [_INNER_PATH]


_TRANSFERS: list[tuple[_Call, str]] = [
    (lambda adapter: adapter.move(_PATH, "b.txt", Config()), "move"),
    (lambda adapter: adapter.copy(_PATH, "b.txt", Config()), "copy"),
]


@pytest.mark.parametrize(("transfer", "expected"), _TRANSFERS, ids=["move", "copy"])
async def test_a_transfer_reaches_both_prefixed_paths(
    transfer: _Call,
    expected: str,
) -> None:
    inner = ScriptedAdapter(files={_INNER_PATH: b"payload"})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    _ = await transfer(adapter)

    assert inner.calls == [f"{expected} {_INNER_PATH}->some/prefix/b.txt"]


_FAILURES: list[tuple[str, StorageOperationFailedError, _Call]] = [
    ("read", UnableToReadFileError(_INNER_PATH, "boom"), lambda adapter: adapter.read(_PATH)),
    ("read_stream", UnableToReadFileError(_INNER_PATH, "boom"), _drain_stream),
    (
        "write",
        UnableToWriteFileError(_INNER_PATH, "boom"),
        lambda adapter: adapter.write(_PATH, b"x", Config()),
    ),
    (
        "write_stream",
        UnableToWriteFileError(_INNER_PATH, "boom"),
        lambda adapter: adapter.write_stream(_PATH, _stream(b"x"), Config()),
    ),
    ("delete", UnableToDeleteFileError(_INNER_PATH, "boom"), lambda adapter: adapter.delete(_PATH)),
    (
        "delete_directory",
        UnableToDeleteDirectoryError(_INNER_PATH, "boom"),
        lambda adapter: adapter.delete_directory(_PATH),
    ),
    (
        "create_directory",
        UnableToCreateDirectoryError(_INNER_PATH, "boom"),
        lambda adapter: adapter.create_directory(_PATH, Config()),
    ),
    (
        "set_visibility",
        UnableToSetVisibilityError(_INNER_PATH, "boom"),
        lambda adapter: adapter.set_visibility(_PATH, Visibility.PUBLIC),
    ),
    (
        "file_exists",
        UnableToCheckFileExistenceError(_INNER_PATH),
        lambda adapter: adapter.file_exists(_PATH),
    ),
    (
        "directory_exists",
        UnableToCheckDirectoryExistenceError(_INNER_PATH),
        lambda adapter: adapter.directory_exists(_PATH),
    ),
    (
        "file_size",
        UnableToRetrieveMetadataError.file_size(_INNER_PATH, "boom"),
        lambda adapter: adapter.file_size(_PATH),
    ),
    (
        "last_modified",
        UnableToRetrieveMetadataError.last_modified(_INNER_PATH),
        lambda adapter: adapter.last_modified(_PATH),
    ),
    ("list_contents", UnableToListContentsError(_INNER_PATH, deep=True), _drain_listing),
]


@pytest.mark.parametrize(
    ("method", "armed", "call"), _FAILURES, ids=[case[0] for case in _FAILURES]
)
async def test_a_failure_is_retold_about_the_path_the_caller_used(
    method: str,
    armed: StorageOperationFailedError,
    call: _Call,
) -> None:
    inner = ScriptedAdapter(files={_INNER_PATH: b"payload"}, fail_on={method: armed})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    with pytest.raises(type(armed)) as raised:
        _ = await call(adapter)

    assert type(raised.value) is type(armed)
    assert _PATH in str(raised.value)
    assert _PREFIX not in str(raised.value)
    assert raised.value.__cause__ is armed


async def test_a_retold_metadata_failure_still_says_what_was_asked_for() -> None:
    armed = UnableToRetrieveMetadataError.mime_type(_INNER_PATH, "boom")
    inner = ScriptedAdapter(files={_INNER_PATH: b"x"}, fail_on={"mime_type": armed})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    with pytest.raises(UnableToRetrieveMetadataError) as raised:
        _ = await adapter.mime_type(_PATH)

    assert raised.value.metadata_type == "mime_type"
    assert raised.value.reason == "boom"


async def test_a_retold_listing_failure_still_says_how_deep_it_reached() -> None:
    armed = UnableToListContentsError(_PREFIX, deep=True)
    inner = ScriptedAdapter(fail_on={"list_contents": armed})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    with pytest.raises(UnableToListContentsError) as raised:
        async for _entry in adapter.list_contents("", deep=True):
            pass

    assert raised.value.location == ""
    assert raised.value.deep


async def test_a_retold_transfer_failure_names_both_caller_paths() -> None:
    armed = UnableToMoveFileError(_INNER_PATH, "some/prefix/b.txt", "boom")
    inner = ScriptedAdapter(files={_INNER_PATH: b"x"}, fail_on={"move": armed})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    with pytest.raises(UnableToMoveFileError) as raised:
        await adapter.move(_PATH, "b.txt", Config())

    assert raised.value.source == _PATH
    assert raised.value.destination == "b.txt"
    assert raised.value.reason == "boom"


async def test_a_failure_of_an_unknown_shape_is_left_alone() -> None:
    armed = _OddShapeError("the backend said something of its own")
    inner = ScriptedAdapter(fail_on={"read": armed})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    with pytest.raises(_OddShapeError) as raised:
        _ = await adapter.read(_PATH)

    assert raised.value is armed


async def test_a_failure_that_is_not_about_a_path_passes_through() -> None:
    armed = FeatureNotSupportedError(Feature.VISIBILITY, "ScriptedAdapter")
    inner = ScriptedAdapter(fail_on={"set_visibility": armed})
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    with pytest.raises(FeatureNotSupportedError) as raised:
        await adapter.set_visibility(_PATH, Visibility.PUBLIC)

    assert raised.value is armed


async def test_it_answers_to_every_capability_a_storage_looks_for() -> None:
    adapter = PathPrefixedAdapter(ScriptedAdapter(), _PREFIX)

    assert isinstance(adapter, StorageAdapterInterface)
    assert isinstance(adapter, ChecksumProviderInterface)
    assert isinstance(adapter, PublicUrlGeneratorInterface)
    assert isinstance(adapter, TemporaryUrlGeneratorInterface)


async def test_it_hands_back_the_wrapped_adapters_checksum() -> None:
    inner = ChecksumScriptedAdapter(
        checksum_value="from-the-backend",
        supported_algorithms=("md5",),
        files={_INNER_PATH: b"x"},
    )
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    assert await adapter.checksum(_PATH, Config()) == "from-the-backend"
    assert inner.received_paths == [_INNER_PATH]


async def test_a_checksum_asks_for_the_fallback_when_the_wrapped_adapter_keeps_none() -> None:
    adapter = PathPrefixedAdapter(ScriptedAdapter(files={_INNER_PATH: b"x"}), _PREFIX)

    with pytest.raises(ChecksumAlgorithmNotSupportedError) as raised:
        _ = await adapter.checksum(_PATH, Config())

    assert raised.value.location == _PATH
    assert raised.value.algorithm == "md5"


async def test_it_hands_back_the_wrapped_adapters_public_url() -> None:
    adapter = PathPrefixedAdapter(PublicUrlScriptedAdapter(files={_INNER_PATH: b"x"}), _PREFIX)

    assert await adapter.public_url(_PATH, Config()) == f"https://backend.example/{_INNER_PATH}"


async def test_a_public_url_is_refused_when_the_wrapped_adapter_has_none() -> None:
    adapter = PathPrefixedAdapter(ScriptedAdapter(files={_INNER_PATH: b"x"}), _PREFIX)

    with pytest.raises(UnableToGeneratePublicUrlError) as raised:
        _ = await adapter.public_url(_PATH, Config())

    assert raised.value.location == _PATH
    assert "wrapped adapter" in raised.value.reason


async def test_it_hands_back_the_wrapped_adapters_temporary_url() -> None:
    adapter = PathPrefixedAdapter(TemporaryUrlScriptedAdapter(files={_INNER_PATH: b"x"}), _PREFIX)

    url = await adapter.temporary_url(_PATH, _EXPIRES_AT, Config())

    assert url.startswith(f"https://backend.example/{_INNER_PATH}?expires=")


async def test_a_temporary_url_is_refused_when_the_wrapped_adapter_signs_none() -> None:
    adapter = PathPrefixedAdapter(ScriptedAdapter(files={_INNER_PATH: b"x"}), _PREFIX)

    with pytest.raises(UnableToGenerateTemporaryUrlError) as raised:
        _ = await adapter.temporary_url(_PATH, _EXPIRES_AT, Config())

    assert raised.value.location == _PATH
    assert "wrapped adapter" in raised.value.reason


async def test_a_storage_over_it_writes_under_the_prefix() -> None:
    inner = ScriptedAdapter()
    storage = Storage(PathPrefixedAdapter(inner, _PREFIX))

    await storage.write("./a.txt", b"payload")

    assert inner.files == {_INNER_PATH: b"payload"}


async def test_closing_closes_the_wrapped_adapter() -> None:
    inner = ScriptedAdapter()
    adapter = PathPrefixedAdapter(inner, _PREFIX)

    await adapter.close()

    assert inner.closed
