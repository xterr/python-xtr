"""The scope entity a grant hands around, which reads as its identifier."""

from __future__ import annotations

from xtr_security_oauth2_server.entities.scope_entity_interface import ScopeEntityInterface
from xtr_security_oauth2_server.entity.scope import Scope


def _scope(identifier: str = "read") -> Scope:
    scope = Scope()
    scope.set_identifier(identifier)

    return scope


def test_it_satisfies_the_scope_contract() -> None:
    assert ScopeEntityInterface in Scope.__mro__
    assert isinstance(_scope(), ScopeEntityInterface)


def test_it_reports_the_identifier_it_was_given() -> None:
    assert _scope().get_identifier() == "read"


def test_it_reads_as_its_identifier_so_a_set_of_them_serialises() -> None:
    assert str(_scope()) == "read"
