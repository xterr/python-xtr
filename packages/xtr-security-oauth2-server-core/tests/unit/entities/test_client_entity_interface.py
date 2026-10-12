"""The client contract is runtime-checkable and includes the grant-type question."""

from __future__ import annotations

from tests.support.entities import User, make_client
from xtr_security_oauth2_server_core.entities.client_entity_interface import ClientEntityInterface


def test_a_client_entity_satisfies_the_contract() -> None:
    client: ClientEntityInterface = make_client()
    assert isinstance(client, ClientEntityInterface)


def test_an_entity_carrying_only_an_identifier_does_not_satisfy_it() -> None:
    assert not isinstance(User(), ClientEntityInterface)


def test_the_contract_declares_the_grant_type_question() -> None:
    client: ClientEntityInterface = make_client()
    assert client.supports_grant_type("authorization_code") is True
