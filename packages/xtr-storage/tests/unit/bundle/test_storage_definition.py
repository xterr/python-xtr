"""Validation of :class:`xtr_storage.bundle.StorageDefinition`."""

from __future__ import annotations

import pytest

from xtr_storage.bundle import LocalAdapterConfig, StorageDefinition
from xtr_storage.exception import (
    InvalidArgumentError,
    InvalidVisibilityError,
    PathTraversalDetectedError,
)


def test_it_defaults_to_a_local_adapter() -> None:
    assert isinstance(StorageDefinition().adapter, LocalAdapterConfig)


def test_it_refuses_a_visibility_that_names_nothing() -> None:
    with pytest.raises(InvalidVisibilityError):
        _ = StorageDefinition(visibility="world")


def test_it_refuses_a_directory_visibility_that_names_nothing() -> None:
    with pytest.raises(InvalidVisibilityError):
        _ = StorageDefinition(directory_visibility="world")


def test_it_refuses_an_empty_prefix() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = StorageDefinition(prefix="")


@pytest.mark.parametrize("prefix", ["..", "../escape", "a/../../b"])
def test_it_refuses_a_prefix_that_climbs_above_the_root(prefix: str) -> None:
    with pytest.raises(PathTraversalDetectedError):
        _ = StorageDefinition(prefix=prefix)


def test_it_normalises_the_prefix_it_stores() -> None:
    assert StorageDefinition(prefix="some//prefix/./").prefix == "some/prefix"


def test_it_refuses_an_empty_public_url() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = StorageDefinition(public_url="")


def test_it_refuses_an_empty_public_url_list() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = StorageDefinition(public_url=[])


def test_it_refuses_a_public_url_list_with_an_empty_entry() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = StorageDefinition(public_url=["https://cdn/", ""])


def test_it_accepts_a_single_public_url() -> None:
    assert StorageDefinition(public_url="https://cdn/").public_url == "https://cdn/"


def test_it_accepts_a_list_of_public_urls() -> None:
    assert StorageDefinition(public_url=["https://a/", "https://b/"]).public_url == [
        "https://a/",
        "https://b/",
    ]
