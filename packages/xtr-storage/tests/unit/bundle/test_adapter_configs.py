"""Validation of the adapter configurations a storage definition picks between."""

from __future__ import annotations

import pytest

from xtr_storage.bundle import (
    FsspecAdapterConfig,
    GcsAdapterConfig,
    LocalAdapterConfig,
    MemoryAdapterConfig,
    S3AdapterConfig,
)
from xtr_storage.exception import InvalidArgumentError, InvalidVisibilityError
from xtr_storage.link_handling import LinkHandling
from xtr_storage.visibility import Visibility


def test_local_defaults_to_a_directory_under_the_project() -> None:
    config = LocalAdapterConfig()

    assert config.directory == "%kernel.project_dir%/var/storage"
    assert config.file_public == 0o644
    assert config.link_handling is LinkHandling.DISALLOW


def test_local_refuses_an_empty_directory() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = LocalAdapterConfig(directory="")


def test_memory_defaults_to_public() -> None:
    assert MemoryAdapterConfig().default_visibility is Visibility.PUBLIC


def test_memory_refuses_a_visibility_that_names_nothing() -> None:
    with pytest.raises(InvalidVisibilityError):
        _ = MemoryAdapterConfig(default_visibility="world")


def test_s3_keeps_its_option_maps_apart() -> None:
    one = S3AdapterConfig(bucket="a")
    two = S3AdapterConfig(bucket="b")

    assert one.client_kwargs == {}
    assert one.client_kwargs is not two.client_kwargs


def test_s3_refuses_an_empty_bucket() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = S3AdapterConfig(bucket="")


def test_gcs_refuses_an_empty_bucket() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = GcsAdapterConfig(bucket="")


def test_fsspec_refuses_an_empty_protocol() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = FsspecAdapterConfig(protocol="")


def test_fsspec_keeps_its_protocol_and_root() -> None:
    config = FsspecAdapterConfig(protocol="memory", root="under")

    assert config.protocol == "memory"
    assert config.root == "under"


def test_the_s3_repr_names_the_bucket_and_no_credential() -> None:
    config = S3AdapterConfig(
        bucket="pictures",
        key="AKIAIOSFODNN7EXAMPLE",
        secret="wJalrXUtnFEMI",  # noqa: S106 -- the example credential from the backend's own documentation, invented to be shown
        token="FwoGZXIvYXdzEExample",  # noqa: S106 -- likewise an invented session token
    )

    rendered = repr(config)

    assert "pictures" in rendered
    assert "AKIAIOSFODNN7EXAMPLE" not in rendered
    assert "wJalrXUtnFEMI" not in rendered
    assert "FwoGZXIvYXdzEExample" not in rendered


def test_the_gcs_repr_names_the_bucket_and_no_credential() -> None:
    config = GcsAdapterConfig(
        bucket="pictures",
        token="ya29.ExampleAccessToken",  # noqa: S106 -- an invented access token, never a real one
    )

    rendered = repr(config)

    assert "pictures" in rendered
    assert "ya29.ExampleAccessToken" not in rendered


def test_a_hidden_credential_is_still_readable_on_the_configuration() -> None:
    config = S3AdapterConfig(bucket="pictures", secret="wJalrXUtnFEMI")  # noqa: S106 -- see above

    assert config.secret == "wJalrXUtnFEMI"  # noqa: S105 -- the invented credential above, compared not stored


def test_the_s3_repr_names_no_option_map() -> None:
    config = S3AdapterConfig(
        bucket="pictures",
        client_kwargs={"aws_session_token": "FwoGZXIvYXdzEExample"},
        config_kwargs={"signature_version": "s3v4-invented"},
        write_options={"ACL": "acl-invented"},
    )

    rendered = repr(config)

    assert "pictures" in rendered
    assert "FwoGZXIvYXdzEExample" not in rendered
    assert "s3v4-invented" not in rendered
    assert "acl-invented" not in rendered


def test_the_gcs_repr_names_no_write_option() -> None:
    config = GcsAdapterConfig(bucket="pictures", write_options={"ContentType": "type-invented"})

    rendered = repr(config)

    assert "pictures" in rendered
    assert "type-invented" not in rendered


def test_the_fsspec_repr_names_no_backend_option() -> None:
    config = FsspecAdapterConfig(protocol="sftp", options={"password": "invented-passphrase"})

    rendered = repr(config)

    assert "sftp" in rendered
    assert "invented-passphrase" not in rendered


def test_a_hidden_option_map_is_still_readable_on_the_configuration() -> None:
    config = FsspecAdapterConfig(protocol="sftp", options={"password": "invented-passphrase"})

    assert config.options == {"password": "invented-passphrase"}
