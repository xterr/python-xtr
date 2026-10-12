"""The scope contract is runtime-checkable and serialises as its identifier."""

from __future__ import annotations

import json

from tests.support.entities import make_scope, make_scopes
from xtr_security_oauth2_server_core.entities.scope_entity_interface import ScopeEntityInterface


def test_a_scope_entity_satisfies_the_contract() -> None:
    scope: ScopeEntityInterface = make_scope("read")
    assert isinstance(scope, ScopeEntityInterface)


def test_a_bare_object_does_not_satisfy_it() -> None:
    assert not isinstance(object(), ScopeEntityInterface)


def test_a_scope_serialises_to_json_as_its_identifier() -> None:
    assert json.dumps(make_scopes("read", "write"), default=str) == '["read", "write"]'
