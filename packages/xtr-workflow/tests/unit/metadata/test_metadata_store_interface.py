"""Anything that reads metadata the four ways a store does is a metadata store."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_workflow.metadata import InMemoryMetadataStore, MetadataStoreInterface

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow import Transition


@final
class _ThreeWays:
    """Reads whole mappings, but not one entry by subject."""

    def get_workflow_metadata(self) -> Mapping[str, object]:
        return {}

    def get_place_metadata(self, place: str) -> Mapping[str, object]:
        return {"place": place}

    def get_transition_metadata(self, transition: Transition) -> Mapping[str, object]:
        return {"transition": transition}


@final
class _FourWays:
    """Reads whole mappings and one entry by subject, deriving from nothing."""

    def get_workflow_metadata(self) -> Mapping[str, object]:
        return {}

    def get_place_metadata(self, place: str) -> Mapping[str, object]:
        return {"place": place}

    def get_transition_metadata(self, transition: Transition) -> Mapping[str, object]:
        return {"transition": transition}

    def get_metadata(self, key: str, subject: str | Transition | None = None) -> object | None:
        return key, subject


def test_the_in_memory_store_satisfies_the_contract() -> None:
    assert isinstance(InMemoryMetadataStore(), MetadataStoreInterface)


def test_an_object_reading_metadata_all_four_ways_satisfies_the_contract() -> None:
    assert isinstance(_FourWays(), MetadataStoreInterface)


def test_an_object_that_cannot_read_one_entry_by_subject_does_not() -> None:
    assert not isinstance(_ThreeWays(), MetadataStoreInterface)
