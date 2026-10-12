"""Turning a scope the protocol handles into one that is stored, and back."""

from __future__ import annotations

from xtr_security_oauth2_server.converter.scope_converter import ScopeConverter
from xtr_security_oauth2_server.converter.scope_converter_interface import (
    ScopeConverterInterface,
)
from xtr_security_oauth2_server.entity.scope import Scope as ScopeEntity
from xtr_security_oauth2_server.value_object.scope import Scope


def _entity(identifier: str) -> ScopeEntity:
    scope = ScopeEntity()
    scope.set_identifier(identifier)

    return scope


def test_it_declares_the_scope_converter_contract() -> None:
    assert ScopeConverterInterface in ScopeConverter.__mro__


def test_it_turns_an_entity_into_the_scope_that_is_stored() -> None:
    assert ScopeConverter().to_domain(_entity("read")) == Scope("read")


def test_it_turns_a_stored_scope_into_the_entity_a_grant_reads() -> None:
    converted = ScopeConverter().to_entity(Scope("read"))

    assert isinstance(converted, ScopeEntity)
    assert converted.get_identifier() == "read"


def test_it_turns_a_whole_sequence_into_stored_scopes_in_order() -> None:
    entities = (_entity("read"), _entity("write"))

    assert ScopeConverter().to_domain_sequence(entities) == (Scope("read"), Scope("write"))


def test_it_turns_a_whole_sequence_into_entities_in_order() -> None:
    converted = ScopeConverter().to_entity_sequence((Scope("read"), Scope("write")))

    assert [scope.get_identifier() for scope in converted] == ["read", "write"]


def test_an_empty_sequence_converts_to_an_empty_sequence() -> None:
    assert ScopeConverter().to_entity_sequence(()) == ()


def test_a_round_trip_changes_nothing() -> None:
    converter = ScopeConverter()

    there_and_back = converter.to_domain_sequence(
        converter.to_entity_sequence((Scope("read"), Scope("write"))),
    )

    assert there_and_back == (Scope("read"), Scope("write"))
