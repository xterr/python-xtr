# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportUnknownParameterType=false, reportMissingParameterType=false, reportUnannotatedClassAttribute=false
# gcsfs and fsspec ship no type information; the fake below subclasses fsspec's
# untyped AsyncFileSystem to stand in for gcsfs without a network, so the
# directives above are confined to this one test module.
"""What the gcs adapter adds to the shared base, proved without a network.

Every behaviour is exercised against an in-test asynchronous filesystem that
stands in for gcsfs: the digests it keeps, the addresses it composes, the
directory markers it writes, the write settings it forwards, the visibility it
refuses, and the session it closes. No test reaches Google.
"""

from __future__ import annotations

import base64
import hashlib
import struct
import sys
import zlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from fsspec.asyn import AsyncFileSystem
from typing_extensions import override

from xtr_storage.adapter.gcs_adapter import GcsAdapter
from xtr_storage.config import Config
from xtr_storage.exception import (
    ChecksumAlgorithmNotSupportedError,
    FeatureNotSupportedError,
    MissingBackendError,
    UnableToCheckDirectoryExistenceError,
    UnableToCreateDirectoryError,
    UnableToGenerateTemporaryUrlError,
    UnableToProvideChecksumError,
)
from xtr_storage.visibility import Visibility

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

pytestmark = pytest.mark.anyio


class _FakeSession:
    """The aiohttp session gcsfs keeps; closing it is all the adapter asks."""

    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class _FakeGcsFileSystem(AsyncFileSystem):
    """A gcsfs stand-in: an in-memory object store with the digests gcs keeps.

    ``cachable = False`` so fsspec's argument-keyed instance cache never hands
    one test's store to the next.
    """

    async_impl = True
    protocol = "fakegcs"
    cachable = False

    def __init__(self, **kwargs) -> None:  # noqa: ANN003
        super().__init__(asynchronous=True)
        del kwargs
        self.asynchronous = True
        self._session = _FakeSession()
        self.store: dict[str, bytes] = {}
        self.meta: dict[str, dict[str, object]] = {}
        self.pipe_calls: list[dict[str, object]] = []
        self.sign_calls: list[tuple[str, int]] = []
        self.sign_error: Exception | None = None
        self.signed_url = "https://storage.example/signed-object"
        self.init_kwargs: dict[str, object] = {}
        self.error: OSError | None = None

    async def _set_session(self) -> _FakeSession:
        return self._session

    def _maybe_fail(self) -> None:
        if self.error is not None:
            raise self.error

    def _record(self, path: str, raw: bytes, content_type: object) -> None:
        self.store[path] = raw
        crc = struct.pack(">I", zlib.crc32(raw) & 0xFFFFFFFF)
        self.meta[path] = {
            "name": path,
            "size": len(raw),
            "type": "file",
            "md5Hash": base64.b64encode(hashlib.md5(raw).digest()).decode(),  # noqa: S324
            "crc32c": base64.b64encode(crc).decode(),
            "contentType": content_type if content_type is not None else "application/octet-stream",
            "updated": "2026-01-01T00:00:00.000Z",
        }

    def _capture(self, path: str, raw: bytes, kwargs: dict[str, object]) -> None:
        content_type = kwargs.get("content_type")
        self.pipe_calls.append(
            {
                "path": path,
                "metadata": kwargs.get("metadata"),
                "content_type": content_type,
                "fixed_key_metadata": kwargs.get("fixed_key_metadata"),
                "extra": {
                    key: value
                    for key, value in kwargs.items()
                    if key not in ("metadata", "content_type", "fixed_key_metadata")
                },
            }
        )
        self._record(path, raw, content_type)

    @override
    async def _pipe_file(self, path, value, mode="overwrite", **kwargs) -> None:  # noqa: ANN001, ANN003
        del mode
        self._maybe_fail()
        self._capture(path, bytes(value), dict(kwargs))

    @override
    async def _put_file(self, lpath, rpath, mode="overwrite", **kwargs) -> None:  # noqa: ANN001, ANN003
        del mode
        with open(lpath, "rb") as handle:  # noqa: ASYNC230, PTH123
            data = handle.read()
        self._capture(rpath, data, dict(kwargs))

    @override
    async def _info(self, path, **kwargs) -> dict[str, object]:  # noqa: ANN001, ANN003
        del kwargs
        self._maybe_fail()
        stripped = path.rstrip("/")
        if stripped in self.meta:
            return dict(self.meta[stripped])
        if any(key.startswith(f"{stripped}/") for key in self.store):
            return {"name": stripped, "size": 0, "type": "directory"}
        raise FileNotFoundError(path)

    @override
    async def _cat_file(self, path, start=None, end=None, **kwargs) -> bytes:  # noqa: ANN001, ANN003
        del kwargs
        if path not in self.store:
            raise FileNotFoundError(path)
        return self.store[path][start:end]

    @override
    async def _exists(self, path, **kwargs) -> bool:  # noqa: ANN001, ANN003
        del kwargs
        self._maybe_fail()
        if path in self.store or path.rstrip("/") in self.store:
            return True
        return any(key.startswith(f"{path.rstrip('/')}/") for key in self.store)

    @override
    async def _ls(self, path, detail=True, **kwargs) -> list[dict[str, object]]:  # noqa: ANN001, ANN003
        del detail, kwargs
        stripped = path.rstrip("/")
        base = f"{stripped}/" if stripped else ""
        matches = [key for key in self.store if not base or key.startswith(base)]
        if not matches:
            raise FileNotFoundError(path)
        entries: list[dict[str, object]] = []
        seen: set[str] = set()
        for key in matches:
            remainder = key[len(base) :]
            if remainder == "":
                entries.append({"name": key, "size": 0, "type": "file"})
                continue
            head = remainder.split("/", 1)[0]
            name = f"{base}{head}"
            if name in seen:
                continue
            seen.add(name)
            if "/" in remainder:
                entries.append({"name": name, "size": 0, "type": "directory"})
            else:
                entries.append(dict(self.meta[key]))
        return entries

    @override
    async def _find(
        self,
        path,  # noqa: ANN001
        maxdepth=None,  # noqa: ANN001
        withdirs=False,  # noqa: ANN001
        **kwargs,  # noqa: ANN003
    ) -> dict[str, dict[str, object]]:
        del maxdepth, withdirs, kwargs
        stripped = path.rstrip("/")
        base = f"{stripped}/" if stripped else ""
        found: dict[str, dict[str, object]] = {}
        for key in self.store:
            if base and not key.startswith(base):
                continue
            if key.endswith("/"):
                found[key] = {"name": key, "size": 0, "type": "directory"}
            else:
                found[key] = dict(self.meta[key])
        return found

    @override
    def sign(self, path, expiration=100, **kwargs) -> str:  # noqa: ANN001, ANN003
        del kwargs
        self.sign_calls.append((path, expiration))
        if self.sign_error is not None:
            raise self.sign_error
        return self.signed_url


async def _stream(*chunks: bytes) -> AsyncIterator[bytes]:
    """Yield the given chunks, as the async source a streamed write takes."""
    for chunk in chunks:
        yield chunk


@pytest.fixture
def gcs_backends(monkeypatch: pytest.MonkeyPatch) -> list[_FakeGcsFileSystem]:
    """Route ``GCSFileSystem`` construction to the fake, recording each build."""
    import gcsfs  # noqa: PLC0415 -- the adapter imports it lazily, so the test patches it lazily too

    created: list[_FakeGcsFileSystem] = []

    def factory(**kwargs: object) -> _FakeGcsFileSystem:
        fake = _FakeGcsFileSystem()
        fake.init_kwargs = dict(kwargs)
        created.append(fake)
        return fake

    monkeypatch.setattr(gcsfs, "GCSFileSystem", factory)
    return created


@pytest.fixture
def adapter(gcs_backends: list[_FakeGcsFileSystem]) -> GcsAdapter:
    """A gcs adapter over a bucket with a prefix, backed by the fake."""
    del gcs_backends
    return GcsAdapter("bucket", "prefix", project="proj", token="anon")  # noqa: S106 -- "anon" is gcsfs's anonymous-access token literal, not a secret


async def test_it_constructs_no_filesystem_until_the_first_operation(
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    _ = GcsAdapter("bucket", "prefix", project="proj", token="anon")  # noqa: S106 -- "anon" is gcsfs's anonymous-access token literal, not a secret

    assert gcs_backends == []


async def test_it_builds_the_client_with_the_documented_options(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"hi", Config())

    kwargs = gcs_backends[0].init_kwargs
    assert kwargs["asynchronous"] is True
    assert kwargs["skip_instance_cache"] is True
    assert kwargs["use_listings_cache"] is False
    assert kwargs["project"] == "proj"
    assert kwargs["token"] == "anon"  # noqa: S105 -- "anon" is gcsfs's anonymous-access token literal, not a secret
    assert kwargs["endpoint_url"] is None


async def test_it_reports_the_md5_digest_as_hex_of_the_stored_hash(
    adapter: GcsAdapter,
) -> None:
    await adapter.write("a.txt", b"the quick brown fox", Config())

    digest = await adapter.checksum("a.txt", Config())

    assert digest == hashlib.md5(b"the quick brown fox").hexdigest()  # noqa: S324


async def test_it_reports_the_crc32c_digest_as_the_backend_keeps_it(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"payload", Config())

    digest = await adapter.checksum("a.txt", Config({Config.CHECKSUM_ALGORITHM: "crc32c"}))

    assert digest == gcs_backends[0].meta["bucket/prefix/a.txt"]["crc32c"]


async def test_it_declines_an_algorithm_it_keeps_no_digest_for(
    adapter: GcsAdapter,
) -> None:
    await adapter.write("a.txt", b"payload", Config())

    with pytest.raises(ChecksumAlgorithmNotSupportedError):
        _ = await adapter.checksum("a.txt", Config({Config.CHECKSUM_ALGORITHM: "sha256"}))


async def test_it_declines_md5_when_the_object_carries_none(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"payload", Config())
    _ = gcs_backends[0].meta["bucket/prefix/a.txt"].pop("md5Hash")

    with pytest.raises(ChecksumAlgorithmNotSupportedError):
        _ = await adapter.checksum("a.txt", Config())


async def test_it_declines_crc32c_when_the_object_carries_none(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"payload", Config())
    _ = gcs_backends[0].meta["bucket/prefix/a.txt"].pop("crc32c")

    with pytest.raises(ChecksumAlgorithmNotSupportedError):
        _ = await adapter.checksum("a.txt", Config({Config.CHECKSUM_ALGORITHM: "crc32c"}))


async def test_it_fails_a_checksum_of_a_missing_file(adapter: GcsAdapter) -> None:
    with pytest.raises(UnableToProvideChecksumError):
        _ = await adapter.checksum("missing.txt", Config())


async def test_it_composes_a_public_url_from_the_default_host(
    adapter: GcsAdapter,
) -> None:
    url = await adapter.public_url("folder/a b.txt", Config())

    assert url == "https://storage.googleapis.com/bucket/prefix/folder/a%20b.txt"


async def test_it_composes_a_public_url_from_an_emulator_endpoint(
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    del gcs_backends
    subject = GcsAdapter("bucket", "prefix", endpoint_url="http://emulator:4443")

    url = await subject.public_url("a.txt", Config())

    assert url == "http://emulator:4443/bucket/prefix/a.txt"


async def test_it_strips_slashes_from_the_bucket_and_prefix(
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    del gcs_backends
    subject = GcsAdapter("/bucket/", "/prefix/")

    url = await subject.public_url("a.txt", Config())

    assert url == "https://storage.googleapis.com/bucket/prefix/a.txt"


async def test_its_mime_type_comes_from_the_name_not_the_stores_stamp(
    adapter: GcsAdapter,
) -> None:
    await adapter.write("a.txt", b"payload", Config())

    assert (await adapter.mime_type("a.txt")).mime_type == "text/plain"


def test_the_token_never_reaches_the_representation() -> None:
    subject = GcsAdapter("bucket", "prefix", token="a-secret-token")  # noqa: S106 -- a stand-in credential asserted to be absent from the repr

    assert "a-secret-token" not in repr(subject)


async def test_it_signs_a_temporary_url(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"payload", Config())
    expires_at = datetime.now(UTC) + timedelta(minutes=5)

    url = await adapter.temporary_url("a.txt", expires_at, Config())

    assert url == "https://storage.example/signed-object"
    signed_path, expiration = gcs_backends[0].sign_calls[0]
    assert signed_path == "bucket/prefix/a.txt"
    assert expiration >= 1


async def test_it_wraps_a_signing_failure(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"payload", Config())
    gcs_backends[0].sign_error = RuntimeError("no credentials")
    expires_at = datetime.now(UTC) + timedelta(minutes=5)

    with pytest.raises(UnableToGenerateTemporaryUrlError) as caught:
        _ = await adapter.temporary_url("a.txt", expires_at, Config())

    assert isinstance(caught.value.__cause__, RuntimeError)


async def test_it_refuses_to_read_a_visibility(adapter: GcsAdapter) -> None:
    with pytest.raises(FeatureNotSupportedError):
        _ = await adapter.visibility("a.txt")


async def test_it_refuses_to_set_a_visibility(adapter: GcsAdapter) -> None:
    with pytest.raises(FeatureNotSupportedError):
        await adapter.set_visibility("a.txt", Visibility.PUBLIC)


async def test_a_write_naming_a_visibility_is_refused(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    with pytest.raises(FeatureNotSupportedError):
        await adapter.write("a.txt", b"payload", Config({Config.VISIBILITY: "public"}))

    assert gcs_backends == []


async def test_a_streamed_write_naming_a_visibility_is_refused(
    adapter: GcsAdapter,
) -> None:
    with pytest.raises(FeatureNotSupportedError):
        await adapter.write_stream(
            "a.txt", _stream(b"payload"), Config({Config.VISIBILITY: "private"})
        )


async def test_a_create_directory_naming_a_visibility_is_refused(
    adapter: GcsAdapter,
) -> None:
    with pytest.raises(FeatureNotSupportedError):
        await adapter.create_directory("docs", Config({Config.DIRECTORY_VISIBILITY: "public"}))


async def test_a_streamed_write_stores_its_bytes(
    adapter: GcsAdapter,
) -> None:
    await adapter.write_stream("a.txt", _stream(b"one ", b"two"), Config())

    assert await adapter.read("a.txt") == b"one two"


async def test_it_creates_a_directory_as_a_zero_byte_marker(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.create_directory("photos", Config())

    assert gcs_backends[0].store["bucket/prefix/photos/"] == b""
    assert await adapter.directory_exists("photos") is True


async def test_a_directory_that_was_never_made_does_not_exist(
    adapter: GcsAdapter,
) -> None:
    assert await adapter.directory_exists("ghost") is False


async def test_creating_the_bucket_root_is_a_no_op(
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    subject = GcsAdapter("bucket", project="proj")

    await subject.create_directory("", Config())

    assert gcs_backends == []


async def test_a_deep_listing_hides_the_directory_markers(
    adapter: GcsAdapter,
) -> None:
    await adapter.create_directory("docs/sub", Config())
    await adapter.write("docs/a.txt", b"payload", Config())

    paths = {entry.path async for entry in adapter.list_contents("docs", deep=True)}

    assert paths == {"docs/a.txt"}


def test_a_trailing_slash_marks_a_hidden_entry(adapter: GcsAdapter) -> None:
    assert adapter._is_hidden_entry("photos/") is True
    assert adapter._is_hidden_entry("photos") is False


async def test_a_write_forwards_only_the_options_the_backend_understands(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write(
        "a.txt",
        b"payload",
        Config(
            {
                "content_type": "text/plain",
                "metadata": {"owner": "me"},
                "cache_control": "no-cache",
                "content_encoding": "gzip",
                "content_disposition": "inline",
                "content_language": "en",
                "storage_class": "COLDLINE",
            }
        ),
    )

    call = gcs_backends[0].pipe_calls[0]
    assert call["content_type"] == "text/plain"
    assert call["metadata"] == {"owner": "me"}
    assert call["fixed_key_metadata"] == {
        "cache_control": "no-cache",
        "content_encoding": "gzip",
        "content_disposition": "inline",
        "content_language": "en",
    }
    assert call["extra"] == {}


async def test_a_plain_write_forwards_no_options(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"payload", Config())

    call = gcs_backends[0].pipe_calls[0]
    assert call["content_type"] is None
    assert call["metadata"] is None
    assert call["fixed_key_metadata"] is None


async def test_default_write_options_apply_unless_a_call_overrides_them(
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    subject = GcsAdapter("bucket", "prefix", write_options={"content_type": "application/pdf"})

    await subject.write("a.txt", b"payload", Config())
    await subject.write("b.txt", b"payload", Config({"content_type": "text/plain"}))

    assert gcs_backends[0].pipe_calls[0]["content_type"] == "application/pdf"
    assert gcs_backends[0].pipe_calls[1]["content_type"] == "text/plain"


async def test_it_names_the_extra_when_the_backend_is_not_installed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "gcsfs", None)
    subject = GcsAdapter("bucket", "prefix")

    with pytest.raises(MissingBackendError) as caught:
        await subject.write("a.txt", b"payload", Config())

    assert caught.value.extra == "gcs"
    assert "xtr-storage[gcs]" in str(caught.value)


async def test_it_opens_a_session_once_and_closes_it_on_close(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"payload", Config())

    await adapter.close()

    assert gcs_backends[0]._session.closed is True


async def test_closing_before_any_operation_does_nothing(adapter: GcsAdapter) -> None:
    await adapter.close()


async def test_closing_twice_is_safe(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"payload", Config())

    await adapter.close()
    await adapter.close()

    assert gcs_backends[0]._session.closed is True


async def test_closing_when_the_store_opened_no_session_does_nothing(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await adapter.write("a.txt", b"payload", Config())
    monkeypatch.setattr(gcs_backends[0], "_session", None)

    await adapter.close()


async def test_a_backend_error_creating_a_directory_is_reported(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("seed.txt", b"seed", Config())
    gcs_backends[0].error = OSError("gcs is down")

    with pytest.raises(UnableToCreateDirectoryError) as caught:
        await adapter.create_directory("photos", Config())

    assert isinstance(caught.value.__cause__, OSError)


async def test_a_backend_error_checking_a_directory_is_reported(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("seed.txt", b"seed", Config())
    gcs_backends[0].error = OSError("gcs is down")

    with pytest.raises(UnableToCheckDirectoryExistenceError) as caught:
        _ = await adapter.directory_exists("photos")

    assert isinstance(caught.value.__cause__, OSError)


async def test_a_backend_error_reading_a_digest_is_reported(
    adapter: GcsAdapter,
    gcs_backends: list[_FakeGcsFileSystem],
) -> None:
    await adapter.write("a.txt", b"payload", Config())
    gcs_backends[0].error = OSError("gcs is down")

    with pytest.raises(UnableToProvideChecksumError) as caught:
        _ = await adapter.checksum("a.txt", Config())

    assert isinstance(caught.value.__cause__, OSError)
