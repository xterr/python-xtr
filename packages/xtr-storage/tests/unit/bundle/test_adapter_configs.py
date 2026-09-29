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
