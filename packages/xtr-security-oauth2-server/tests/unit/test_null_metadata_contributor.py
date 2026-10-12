"""The one contributor every deployment has, so the collection is never empty."""

from __future__ import annotations

from xtr_security_oauth2_server.metadata_contributor_interface import (
    MetadataContributorInterface,
)
from xtr_security_oauth2_server.null_metadata_contributor import NullMetadataContributor


def test_it_declares_the_contributor_contract() -> None:
    assert MetadataContributorInterface in NullMetadataContributor.__mro__


def test_it_contributes_no_field_at_all() -> None:
    # Nothing can be injected as an empty collection, and the ordinary
    # deployment has no extension adding fields to its description.
    assert dict(NullMetadataContributor().get_metadata()) == {}


def test_what_it_answers_cannot_be_written_into() -> None:
    # One shared mapping: a contributor reaching into it would change what
    # every other one is handed.
    assert NullMetadataContributor().get_metadata() is NullMetadataContributor().get_metadata()


def test_it_names_the_type_which_is_the_whole_of_what_there_is_to_say() -> None:
    assert repr(NullMetadataContributor()) == "NullMetadataContributor()"
