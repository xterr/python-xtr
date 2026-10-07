from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO, StringIO
from typing import TYPE_CHECKING, cast, final

import pytest
from fsspec.asyn import (  # pyright: ignore[reportMissingTypeStubs] -- fsspec ships no type information; imported only to shape the copy-then-delete fake below
    AsyncFileSystem,
)
from typing_extensions import override

from tests.support.scripted_adapter import (
    ChecksumScriptedAdapter,
    PublicUrlScriptedAdapter,
    ScriptedAdapter,
    TemporaryUrlScriptedAdapter,
)
from xtr_storage.adapter.generic_fsspec_adapter import GenericFsspecAdapter
from xtr_storage.adapter.in_memory_adapter import InMemoryAdapter
from xtr_storage.adapter.local_adapter import LocalAdapter
from xtr_storage.config import Config
from xtr_storage.exception import (
    FeatureNotSupportedError,
    InvalidArgumentError,
    InvalidStreamError,
    UnableToCopyFileError,
    UnableToGeneratePublicUrlError,
    UnableToGenerateTemporaryUrlError,
    UnableToListContentsError,
    UnableToMoveFileError,
)
from xtr_storage.feature import Feature
from xtr_storage.storage import Storage
from xtr_storage.storage_operator_interface import StorageOperatorInterface
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path
    from typing import BinaryIO

    from xtr_storage.config import Config as ConfigType

pytestmark = pytest.mark.anyio

_FOOBAR_MD5 = "3858f62230ac3c915f300c664312c63f"


class FixedPublicUrlGenerator:
    """An injected public-url generator that always answers the same address."""

    def __init__(self, url: str) -> None:
        self.url: str = url
        self.calls: list[str] = []

    async def public_url(self, path: str, config: ConfigType) -> str:
        del config
        self.calls.append(path)

        return self.url


class FixedTemporaryUrlGenerator:
    """An injected temporary-url generator that always answers the same address."""

    def __init__(self, url: str) -> None:
        self.url: str = url
        self.calls: list[str] = []

    async def temporary_url(self, path: str, expires_at: datetime, config: ConfigType) -> str:
        del expires_at, config
        self.calls.append(path)

        return self.url


def test_a_storage_satisfies_the_operator_interface() -> None:
    assert isinstance(Storage(ScriptedAdapter()), StorageOperatorInterface)


# --- path normalization reaches the adapter ---------------------------------


async def test_a_write_reaches_the_adapter_at_the_normalized_path() -> None:
    adapter = ScriptedAdapter()
    storage = Storage(adapter)

    await storage.write("a/./b//c/../d", b"x")

    assert "a/b/d" in adapter.files


async def test_every_read_method_normalizes_before_delegating() -> None:
    adapter = ScriptedAdapter(files={"a/b": b"x"}, visibility={"a/b": Visibility.PUBLIC})
    storage = Storage(adapter)

    _ = await storage.read("/a/b")
    _ = await storage.file_exists("a//b")
    _ = await storage.directory_exists("a/./b")

    assert adapter.received_paths == ["a/b", "a/b", "a/b"]


# --- identical-path policy: copy --------------------------------------------


async def test_copy_to_the_same_path_fails_when_asked_to() -> None:
    storage = Storage(ScriptedAdapter(files={"a": b"x"}))

    with pytest.raises(UnableToCopyFileError):
        await storage.copy("a", "a", {Config.COPY_IDENTICAL_PATH: "fail"})


async def test_copy_to_the_same_path_is_ignored_when_asked_to() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter)

    await storage.copy("a", "a", {Config.COPY_IDENTICAL_PATH: "ignore"})

    assert "copy a->a" not in adapter.calls


async def test_copy_to_the_same_path_reaches_the_backend_when_asked_to() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter)

    await storage.copy("a", "a", {Config.COPY_IDENTICAL_PATH: "try"})

    assert "copy a->a" in adapter.calls


async def test_copy_to_the_same_path_is_ignored_by_default() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter)

    await storage.copy("a", "a")

    assert "copy a->a" not in adapter.calls


async def test_copy_to_the_same_missing_path_still_reports_the_missing_source() -> None:
    adapter = ScriptedAdapter()
    storage = Storage(adapter)

    with pytest.raises(UnableToCopyFileError) as caught:
        await storage.copy("ghost", "ghost")

    assert caught.value.reason == "the source file does not exist"
    assert "copy ghost->ghost" not in adapter.calls


# --- identical-path policy: move --------------------------------------------


async def test_move_to_the_same_path_fails_when_asked_to() -> None:
    storage = Storage(ScriptedAdapter(files={"a": b"x"}))

    with pytest.raises(UnableToMoveFileError):
        await storage.move("a", "a", {Config.MOVE_IDENTICAL_PATH: "fail"})


async def test_move_to_the_same_path_is_ignored_when_asked_to() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter)

    await storage.move("a", "a", {Config.MOVE_IDENTICAL_PATH: "ignore"})

    assert "move a->a" not in adapter.calls


async def test_move_to_the_same_path_reaches_the_backend_when_asked_to() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter)

    await storage.move("a", "a", {Config.MOVE_IDENTICAL_PATH: "try"})

    assert "move a->a" in adapter.calls


async def test_move_to_the_same_path_is_ignored_by_default() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter)

    await storage.move("a", "a")

    assert "move a->a" not in adapter.calls


async def test_move_to_the_same_missing_path_still_reports_the_missing_source() -> None:
    adapter = ScriptedAdapter()
    storage = Storage(adapter)

    with pytest.raises(UnableToMoveFileError) as caught:
        await storage.move("ghost", "ghost")

    assert caught.value.reason == "the source file does not exist"
    assert "move ghost->ghost" not in adapter.calls


# --- identical-path policy: the default over the adapters this package ships -


async def test_copy_to_the_same_path_keeps_the_file_in_memory() -> None:
    storage = Storage(InMemoryAdapter())
    await storage.write("a.txt", b"payload")

    await storage.copy("a.txt", "a.txt")

    assert await storage.read("a.txt") == b"payload"


async def test_move_to_the_same_path_keeps_the_file_in_memory() -> None:
    storage = Storage(InMemoryAdapter())
    await storage.write("a.txt", b"payload")

    await storage.move("a.txt", "a.txt")

    assert await storage.read("a.txt") == b"payload"


async def test_copy_to_the_same_path_keeps_the_file_on_disk(tmp_path: Path) -> None:
    storage = Storage(LocalAdapter(tmp_path / "root"))
    await storage.write("a.txt", b"payload")

    await storage.copy("a.txt", "a.txt")

    assert await storage.read("a.txt") == b"payload"


async def test_move_to_the_same_path_keeps_the_file_on_disk(tmp_path: Path) -> None:
    storage = Storage(LocalAdapter(tmp_path / "root"))
    await storage.write("a.txt", b"payload")

    await storage.move("a.txt", "a.txt")

    assert await storage.read("a.txt") == b"payload"


@final
class _CopyThenDeleteFileSystem(AsyncFileSystem):
    """An object store's shape: asynchronous, and moving by copy-then-delete.

    An asynchronous filesystem that names no ``_mv`` — s3fs and gcsfs are two,
    and the adapters over them drive the asynchronous dialect — gets its move
    from a copy followed by a delete of the source. When the two paths are one
    path, the copy writes what is already there and the delete then takes it
    away. This fake is the smallest backend of that shape.
    """

    protocol = "copythendelete"
    cachable = False

    def __init__(self) -> None:
        super().__init__(asynchronous=True)  # pyright: ignore[reportUnknownMemberType] -- fsspec ships no type information, so its initializer is untyped
        self.store: dict[str, bytes] = {}

    @override
    async def _pipe_file(
        self, path: str, value: bytes, mode: str = "overwrite", **kwargs: object
    ) -> None:
        del mode, kwargs
        self.store[path] = bytes(value)

    @override
    async def _cat_file(
        self, path: str, start: int | None = None, end: int | None = None, **kwargs: object
    ) -> bytes:
        del kwargs
        if path not in self.store:
            raise FileNotFoundError(path)
        return self.store[path][start:end]

    @override
    async def _cp_file(self, path1: str, path2: str, **kwargs: object) -> None:
        del kwargs
        self.store[path2] = self.store[path1]

    @override
    async def _rm_file(self, path: str, **kwargs: object) -> list[None]:
        """Delete one file, answering with the empty gathering the base promises."""
        del kwargs
        del self.store[path]
        return []

    @override
    async def _info(self, path: str, **kwargs: object) -> dict[str, object]:
        del kwargs
        if path not in self.store:
            raise FileNotFoundError(path)
        return {"name": path, "size": len(self.store[path]), "type": "file"}


async def test_move_to_the_same_path_keeps_the_file_on_a_copy_then_delete_backend() -> None:
    # The one backend shape where the old default destroyed the file: the copy
    # rewrites what is already there, and the delete of the source removes it.
    storage = Storage(GenericFsspecAdapter(_CopyThenDeleteFileSystem()))
    await storage.write("a.txt", b"payload")

    await storage.move("a.txt", "a.txt")

    assert await storage.read("a.txt") == b"payload"


# --- retain-visibility stripping --------------------------------------------


async def test_a_transfer_drops_the_default_visibility_to_keep_the_source_one() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter, {Config.VISIBILITY: "private"})

    await storage.copy("a", "b")

    transfer_config = adapter.received_configs[-1]
    assert transfer_config.get(Config.VISIBILITY) is None


async def test_a_transfer_keeps_a_visibility_the_call_named() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter, {Config.VISIBILITY: "private"})

    await storage.copy("a", "b", {Config.VISIBILITY: "public"})

    transfer_config = adapter.received_configs[-1]
    assert transfer_config.get(Config.VISIBILITY) == "public"


async def test_a_transfer_keeps_the_default_visibility_when_retaining_is_off() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter, {Config.VISIBILITY: "private"})

    await storage.copy("a", "b", {Config.RETAIN_VISIBILITY: False})

    transfer_config = adapter.received_configs[-1]
    assert transfer_config.get(Config.VISIBILITY) == "private"


# --- checksum ----------------------------------------------------------------


async def test_a_non_provider_adapter_streams_the_checksum() -> None:
    adapter = ScriptedAdapter(files={"f": b"foobar"})
    storage = Storage(adapter)

    assert await storage.checksum("f") == _FOOBAR_MD5


async def test_a_provider_answers_the_checksum_for_a_supported_algorithm() -> None:
    adapter = ChecksumScriptedAdapter(checksum_value="etag-value", supported_algorithms=("etag",))
    storage = Storage(adapter)

    assert await storage.checksum("f", {Config.CHECKSUM_ALGORITHM: "etag"}) == "etag-value"


async def test_a_provider_that_cannot_answer_falls_back_to_streaming() -> None:
    adapter = ChecksumScriptedAdapter(files={"f": b"foobar"}, supported_algorithms=("etag",))
    storage = Storage(adapter)

    assert await storage.checksum("f") == _FOOBAR_MD5


async def test_an_unknown_checksum_algorithm_is_refused() -> None:
    adapter = ScriptedAdapter(files={"f": b"foobar"})
    storage = Storage(adapter)

    with pytest.raises(InvalidArgumentError):
        _ = await storage.checksum("f", {Config.CHECKSUM_ALGORITHM: "no-such-algorithm"})


# --- public_url resolution order --------------------------------------------


async def test_public_url_prefers_the_injected_generator() -> None:
    generator = FixedPublicUrlGenerator("https://injected.example/x")
    adapter = PublicUrlScriptedAdapter()
    storage = Storage(
        adapter,
        {Config.PUBLIC_URL: "https://config.example/"},
        public_url_generator=generator,
    )

    assert await storage.public_url("a.txt") == "https://injected.example/x"
    assert generator.calls == ["a.txt"]


async def test_public_url_then_uses_a_single_config_prefix() -> None:
    storage = Storage(
        PublicUrlScriptedAdapter(),
        {Config.PUBLIC_URL: "https://config.example/"},
    )

    assert await storage.public_url("a/b.txt") == "https://config.example/a/b.txt"


async def test_public_url_shards_across_a_config_list() -> None:
    prefixes = ["https://one.example/", "https://two.example/"]
    storage = Storage(PublicUrlScriptedAdapter(), {Config.PUBLIC_URL: prefixes})

    url = await storage.public_url("a/b.txt")

    assert url in {"https://one.example/a/b.txt", "https://two.example/a/b.txt"}


async def test_public_url_then_falls_to_the_adapter() -> None:
    storage = Storage(PublicUrlScriptedAdapter())

    assert await storage.public_url("a.txt") == "https://backend.example/a.txt"


async def test_public_url_refuses_when_nothing_can_build_one() -> None:
    storage = Storage(ScriptedAdapter())

    with pytest.raises(UnableToGeneratePublicUrlError):
        _ = await storage.public_url("a.txt")


async def test_a_bad_public_url_option_is_refused() -> None:
    storage = Storage(ScriptedAdapter(), {Config.PUBLIC_URL: 123})

    with pytest.raises(InvalidArgumentError):
        _ = await storage.public_url("a.txt")


# --- temporary_url -----------------------------------------------------------


async def test_temporary_url_refuses_a_naive_deadline() -> None:
    storage = Storage(TemporaryUrlScriptedAdapter())

    with pytest.raises(InvalidArgumentError):
        _ = await storage.temporary_url("a.txt", datetime(2030, 1, 1))  # noqa: DTZ001


async def test_temporary_url_uses_the_adapter_capability() -> None:
    storage = Storage(TemporaryUrlScriptedAdapter())
    expires_at = datetime(2030, 1, 1, tzinfo=UTC)

    url = await storage.temporary_url("a.txt", expires_at)

    assert url == f"https://backend.example/a.txt?expires={int(expires_at.timestamp())}"


async def test_temporary_url_prefers_the_injected_generator() -> None:
    generator = FixedTemporaryUrlGenerator("https://injected.example/temp")
    storage = Storage(TemporaryUrlScriptedAdapter(), temporary_url_generator=generator)

    url = await storage.temporary_url("a.txt", datetime(2030, 1, 1, tzinfo=UTC))

    assert url == "https://injected.example/temp"


async def test_temporary_url_refuses_when_nothing_can_sign() -> None:
    storage = Storage(ScriptedAdapter())

    with pytest.raises(UnableToGenerateTemporaryUrlError):
        _ = await storage.temporary_url("a.txt", datetime(2030, 1, 1, tzinfo=UTC))


# --- write_stream sources ----------------------------------------------------


async def test_write_stream_rewinds_a_seekable_binary_file() -> None:
    adapter = ScriptedAdapter()
    storage = Storage(adapter)
    handle = BytesIO(b"foobar")
    _ = handle.seek(3)

    await storage.write_stream("f", handle)

    assert adapter.files["f"] == b"foobar"


async def test_write_stream_accepts_an_iterable_of_chunks() -> None:
    adapter = ScriptedAdapter()
    storage = Storage(adapter)

    await storage.write_stream("f", [b"foo", b"bar"])

    assert adapter.files["f"] == b"foobar"


async def test_write_stream_refuses_text() -> None:
    storage = Storage(ScriptedAdapter())

    with pytest.raises(InvalidStreamError):
        await storage.write_stream("f", cast("Iterable[bytes]", "foobar"))


async def test_write_stream_refuses_raw_bytes() -> None:
    storage = Storage(ScriptedAdapter())

    with pytest.raises(InvalidStreamError):
        await storage.write_stream("f", cast("Iterable[bytes]", b"foobar"))


async def test_write_stream_refuses_a_text_file_object() -> None:
    storage = Storage(ScriptedAdapter())

    with pytest.raises(InvalidStreamError):
        await storage.write_stream("f", cast("BinaryIO", cast("object", StringIO("foobar"))))


# --- listing errors are wrapped lazily --------------------------------------


async def test_listing_does_not_touch_the_backend_until_iterated() -> None:
    adapter = ScriptedAdapter(fail_on={"list_contents": RuntimeError("boom")})
    storage = Storage(adapter)

    _ = storage.list_contents("dir", deep=True)

    assert "list_contents dir" not in adapter.calls


async def test_a_listing_failure_becomes_the_listing_error_with_its_cause() -> None:
    boom = RuntimeError("boom")
    adapter = ScriptedAdapter(fail_on={"list_contents": boom})
    storage = Storage(adapter)

    with pytest.raises(UnableToListContentsError) as caught:
        _ = await storage.list_contents("dir", deep=True).to_list()

    assert caught.value.__cause__ is boom
    assert caught.value.deep is True


async def test_an_unsupported_listing_passes_through_unwrapped() -> None:
    unsupported = FeatureNotSupportedError(Feature.VISIBILITY, "ScriptedAdapter")
    adapter = ScriptedAdapter(fail_on={"list_contents": unsupported})
    storage = Storage(adapter)

    with pytest.raises(FeatureNotSupportedError):
        _ = await storage.list_contents("dir").to_list()


async def test_a_listing_yields_the_entries_the_adapter_reports() -> None:
    adapter = ScriptedAdapter(files={"dir/a.txt": b"1", "dir/b.txt": b"2"})
    storage = Storage(adapter)

    paths = [entry.path async for entry in storage.list_contents("dir")]

    assert paths == ["dir/a.txt", "dir/b.txt"]


# --- close and context management -------------------------------------------


async def test_close_closes_the_adapter() -> None:
    adapter = ScriptedAdapter()
    storage = Storage(adapter)

    await storage.close()

    assert adapter.closed


async def test_the_context_manager_closes_on_exit() -> None:
    adapter = ScriptedAdapter()

    async with Storage(adapter) as storage:
        await storage.write("a.txt", b"x")

    assert adapter.closed


# --- metadata delegation -----------------------------------------------------


async def test_metadata_reads_normalize_and_return_the_bare_value() -> None:
    adapter = ScriptedAdapter(files={"a/b": b"hello"}, visibility={"a/b": Visibility.PRIVATE})
    storage = Storage(adapter)

    assert await storage.file_size("/a/b") == 5
    assert await storage.mime_type("a//b") == "text/plain"
    assert await storage.last_modified("a/b") == 1_700_000_000
    assert await storage.visibility("a/b") is Visibility.PRIVATE


async def test_set_visibility_parses_a_name_before_delegating() -> None:
    adapter = ScriptedAdapter(files={"a": b"x"})
    storage = Storage(adapter)

    await storage.set_visibility("a", "private")

    assert adapter.visibilities["a"] is Visibility.PRIVATE
