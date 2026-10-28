"""A store that reads whole metadata mappings reads one entry by subject through the trait."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from xtr_workflow import Transition
from xtr_workflow.exception import InvalidArgumentError
from xtr_workflow.metadata import GetMetadataTrait, MetadataStoreInterface

if TYPE_CHECKING:
    from collections.abc import Mapping


@final
class _Store(GetMetadataTrait):
    """Answers each getter with an entry naming it, so a lookup shows which one it went through."""

    @override
    def get_workflow_metadata(self) -> Mapping[str, object]:
        return {"read": "workflow"}

    @override
    def get_place_metadata(self, place: str) -> Mapping[str, object]:
        return {"read": f"place {place}"}

    @override
    def get_transition_metadata(self, transition: Transition) -> Mapping[str, object]:
        return {"read": f"transition {transition.get_name()}"}


def test_a_store_using_it_is_a_metadata_store() -> None:
    assert isinstance(_Store(), MetadataStoreInterface)


def test_no_subject_reads_the_workflow_metadata() -> None:
    assert _Store().get_metadata("read") == "workflow"


def test_a_place_name_reads_the_metadata_of_that_place() -> None:
    assert _Store().get_metadata("read", "place_a") == "place place_a"


def test_a_transition_reads_the_metadata_of_that_transition() -> None:
    assert _Store().get_metadata("read", Transition("submit", "a", "b")) == "transition submit"


def test_an_entry_the_metadata_lacks_is_none() -> None:
    assert _Store().get_metadata("description", "place_a") is None


def test_a_subject_that_is_neither_a_place_nor_a_transition_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = _Store().get_metadata("read", True)  # ty: ignore[invalid-argument-type] # pyright: ignore[reportArgumentType] — a wrong subject is what the check refuses

    assert str(raised.value) == 'Could not find a MetadataBag for the subject of type "bool".'
