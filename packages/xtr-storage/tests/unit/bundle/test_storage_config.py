"""Validation and reading of :class:`xtr_storage.bundle.StorageConfig`."""

from __future__ import annotations

from typing import cast

import pytest

from xtr_storage.bundle import (
    DEFAULT_STORAGE,
    MemoryAdapterConfig,
    StorageConfig,
    StorageDefinition,
)
from xtr_storage.exception import InvalidArgumentError


def test_the_default_is_one_storage_named_default() -> None:
    definitions = StorageConfig().definitions()

    assert set(definitions) == {DEFAULT_STORAGE}
    assert isinstance(definitions[DEFAULT_STORAGE], StorageDefinition)


def test_an_empty_mapping_reads_as_the_default() -> None:
    definitions = StorageConfig(storages={}).definitions()

    assert set(definitions) == {DEFAULT_STORAGE}


def test_a_bare_adapter_configuration_is_wrapped_in_a_definition() -> None:
    config = StorageConfig(storages={"memory": MemoryAdapterConfig()})

    definition = config.definitions()["memory"]

    assert isinstance(definition, StorageDefinition)
    assert isinstance(definition.adapter, MemoryAdapterConfig)


def test_a_definition_is_read_as_it_is() -> None:
    definition = StorageDefinition(adapter=MemoryAdapterConfig(), read_only=True)
    config = StorageConfig(storages={"memory": definition})

    assert config.definitions()["memory"] is definition


def test_it_refuses_a_storage_without_a_name() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = StorageConfig(storages={"": MemoryAdapterConfig()})


def test_it_refuses_an_entry_that_is_neither_a_definition_nor_an_adapter() -> None:
    bad = cast("StorageDefinition", cast("object", "just a string"))
    with pytest.raises(InvalidArgumentError):
        _ = StorageConfig(storages={"bad": bad})
