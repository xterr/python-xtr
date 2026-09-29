"""The s3 adapter's behaviour that needs no store: urls, options, imports.

Everything here is decided before a request would leave the process — a url is
composed from the bucket, write options are filtered in memory, the default
checksum algorithm is refused up front, and a missing backend fails on the first
build — so none of it touches a network, and the constructor is proven to touch
nothing at all.
"""

from __future__ import annotations

import sys

import pytest

from xtr_storage.adapter.s3_adapter import S3Adapter
from xtr_storage.config import Config
from xtr_storage.exception import ChecksumAlgorithmNotSupportedError, MissingBackendError
from xtr_storage.visibility import Visibility

pytestmark = pytest.mark.anyio


def test_the_constructor_opens_nothing() -> None:
    subject = S3Adapter("bucket", key="id", secret="shh")  # noqa: S106 -- a stand-in credential for a test that opens nothing

    assert subject._bridge is None


def test_a_missing_backend_names_the_extra_to_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "s3fs", None)
    subject = S3Adapter("bucket")

    with pytest.raises(MissingBackendError) as caught:
        _ = subject._create_filesystem()

    assert caught.value.package == "s3fs"
    assert "xtr-storage[s3]" in str(caught.value)


async def test_it_composes_a_virtual_hosted_public_url() -> None:
    subject = S3Adapter("photos", region="eu-west-1")

    url = await subject.public_url("holiday/beach.jpg", Config())

    assert url == "https://photos.s3.eu-west-1.amazonaws.com/holiday/beach.jpg"


async def test_a_public_url_defaults_to_the_home_region() -> None:
    subject = S3Adapter("photos")

    url = await subject.public_url("a.txt", Config())

    assert url == "https://photos.s3.us-east-1.amazonaws.com/a.txt"


async def test_it_composes_a_path_style_public_url_under_an_endpoint() -> None:
    subject = S3Adapter("photos", endpoint_url="http://127.0.0.1:9000/")

    url = await subject.public_url("a.txt", Config())

    assert url == "http://127.0.0.1:9000/photos/a.txt"


async def test_a_public_url_quotes_reserved_characters_and_keeps_slashes() -> None:
    subject = S3Adapter("photos", region="eu-west-1")

    url = await subject.public_url("we ird/[a] {b} c.txt", Config())

    assert url == ("https://photos.s3.eu-west-1.amazonaws.com/we%20ird/%5Ba%5D%20%7Bb%7D%20c.txt")


async def test_a_prefix_is_part_of_the_public_url_key() -> None:
    subject = S3Adapter("photos", "albums/2026", region="eu-west-1")

    url = await subject.public_url("a.txt", Config())

    assert url == "https://photos.s3.eu-west-1.amazonaws.com/albums/2026/a.txt"


def test_the_write_options_drop_keys_the_backend_has_no_name_for() -> None:
    subject = S3Adapter(
        "bucket",
        write_options={"ContentType": "text/plain", "Bogus": "x", "StorageClass": "GLACIER"},
    )

    options = subject._write_options(Config())

    assert options == {"ContentType": "text/plain", "StorageClass": "GLACIER"}


def test_a_public_visibility_becomes_a_public_read_access_list() -> None:
    subject = S3Adapter("bucket")

    options = subject._write_options(Config({Config.VISIBILITY: Visibility.PUBLIC.value}))

    assert options["ACL"] == "public-read"


def test_a_private_visibility_becomes_a_private_access_list() -> None:
    subject = S3Adapter("bucket")

    options = subject._write_options(Config({Config.VISIBILITY: Visibility.PRIVATE.value}))

    assert options["ACL"] == "private"


def test_a_guessed_media_type_fills_in_a_missing_content_type() -> None:
    subject = S3Adapter("bucket")
    hinted = subject._with_detected_type("logo.svg", Config())

    options = subject._write_options(hinted)

    assert options["ContentType"] == "image/svg+xml"


def test_a_configured_content_type_outranks_the_guessed_one() -> None:
    subject = S3Adapter("bucket", write_options={"ContentType": "application/octet-stream"})
    hinted = subject._with_detected_type("logo.svg", Config())

    options = subject._write_options(hinted)

    assert options["ContentType"] == "application/octet-stream"


async def test_the_default_algorithm_is_refused_so_the_storage_hashes_instead() -> None:
    subject = S3Adapter("bucket")

    with pytest.raises(ChecksumAlgorithmNotSupportedError) as caught:
        _ = await subject.checksum("a.txt", Config())

    assert caught.value.algorithm == "md5"


async def test_a_named_algorithm_other_than_etag_is_refused() -> None:
    subject = S3Adapter("bucket")

    with pytest.raises(ChecksumAlgorithmNotSupportedError):
        _ = await subject.checksum("a.txt", Config({Config.CHECKSUM_ALGORITHM: "sha256"}))


def test_credentials_never_reach_the_representation() -> None:
    subject = S3Adapter(
        "bucket",
        key="AKIAsecretid",
        secret="topsecret",  # noqa: S106 -- a stand-in credential asserted to be absent from the repr
        token="sessiontoken",  # noqa: S106 -- a stand-in credential asserted to be absent from the repr
    )

    shown = repr(subject)

    assert "AKIAsecretid" not in shown
    assert "topsecret" not in shown
    assert "sessiontoken" not in shown


def test_configured_write_options_are_copied_not_aliased() -> None:
    source: dict[str, object] = {"StorageClass": "GLACIER"}
    subject = S3Adapter("bucket", write_options=source)

    source["StorageClass"] = "STANDARD"

    assert subject._write_options(Config()) == {"StorageClass": "GLACIER"}
