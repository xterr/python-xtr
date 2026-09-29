"""The s3 adapter, held to the contract every adapter answers, over a real store.

Every behaviour here runs against a local object store bound to a loose port, so
it lives among the integration tests: writes, listings, access lists and signed
urls all cross HTTP to a backend that behaves as the real one does. Each test
gets a bucket of its own, created through the adapter before the test begins and
the session closed after, so a leaked client would fail the test that leaked it.
"""

from __future__ import annotations

import gc
import hashlib
from typing import TYPE_CHECKING, ClassVar
from uuid import uuid4

import pytest

from tests.support.adapter_conformance import AdapterConformance
from tests.support.moto_server import create_bucket, make_bucket_public
from xtr_storage.adapter.s3_adapter import S3Adapter
from xtr_storage.config import Config
from xtr_storage.exception import UnableToReadFileError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_storage.adapter.storage_adapter_interface import StorageAdapterInterface

pytestmark = pytest.mark.anyio


@pytest.fixture
async def s3_adapter(moto_endpoint: str) -> AsyncIterator[S3Adapter]:
    """Yield an adapter over a bucket of this test's own, closed when it ends.

    The bucket is made anonymously readable so a composed public url resolves
    over HTTP, as it would against a bucket a deployment publishes; object-level
    access lists, which the visibility tests round-trip, are independent of it.
    """
    bucket = f"test-{uuid4().hex}"
    subject = S3Adapter(
        bucket,
        region="us-east-1",
        endpoint_url=moto_endpoint,
        key="testing",
        secret="testing",  # noqa: S106 -- the local stand-in's fixed test credential, never a real secret
    )
    await create_bucket(subject, bucket)
    await make_bucket_public(subject, bucket)
    try:
        yield subject
    finally:
        await subject.close()


class TestS3AdapterConformance(AdapterConformance):
    """Every shared behaviour, over a bucket this test alone can reach."""

    supports_visibility: ClassVar[bool] = True
    http_fetch: ClassVar[bool] = True

    @pytest.fixture
    async def adapter(self, s3_adapter: S3Adapter) -> StorageAdapterInterface:
        return s3_adapter


async def test_the_etag_checksum_is_the_stored_entity_tag(s3_adapter: S3Adapter) -> None:
    await s3_adapter.write("digest.txt", b"digest me", Config())

    digest = await s3_adapter.checksum("digest.txt", Config({Config.CHECKSUM_ALGORITHM: "etag"}))

    assert digest == hashlib.md5(b"digest me").hexdigest()  # noqa: S324 -- the entity tag a store keeps for a single-part upload is an md5, matched here


async def test_reading_a_missing_key_raises_unable_to_read(s3_adapter: S3Adapter) -> None:
    with pytest.raises(UnableToReadFileError):
        _ = await s3_adapter.read("nowhere/gone.txt")


async def test_a_marker_directory_is_listed_once_and_its_marker_hidden(
    s3_adapter: S3Adapter,
) -> None:
    await s3_adapter.create_directory("folder", Config())
    await s3_adapter.write("folder/file.txt", b"a", Config())

    top = [entry async for entry in s3_adapter.list_contents("", deep=False)]
    inside = [entry async for entry in s3_adapter.list_contents("folder", deep=False)]

    directories = [entry for entry in top if entry.is_dir and entry.path == "folder"]
    assert len(directories) == 1
    assert all(entry.path != "folder" for entry in inside)
    assert any(entry.path == "folder/file.txt" for entry in inside)


async def test_closing_after_one_operation_leaves_no_open_session(
    moto_endpoint: str,
) -> None:
    # A leaked client session surfaces as a warning the suite turns into a
    # failure; forcing collection makes it land on this test rather than a later.
    bucket = f"test-{uuid4().hex}"
    subject = S3Adapter(
        bucket,
        region="us-east-1",
        endpoint_url=moto_endpoint,
        key="testing",
        secret="testing",  # noqa: S106 -- the local stand-in's fixed test credential, never a real secret
    )
    await create_bucket(subject, bucket)
    await subject.write("only.txt", b"once", Config())

    await subject.close()

    del subject
    for _ in range(3):
        _ = gc.collect()
