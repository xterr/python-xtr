"""The authorization-code contract is runtime-checkable."""

from __future__ import annotations

from tests.support.entities import AccessToken, AuthCode
from xtr_security_oauth2_server.entities.auth_code_entity_interface import AuthCodeEntityInterface


def test_an_auth_code_entity_satisfies_the_contract() -> None:
    code: AuthCodeEntityInterface = AuthCode()
    assert isinstance(code, AuthCodeEntityInterface)


def test_a_token_carrying_no_redirect_uri_does_not_satisfy_it() -> None:
    assert not isinstance(AccessToken(), AuthCodeEntityInterface)
