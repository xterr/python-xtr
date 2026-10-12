"""The access-token contract is runtime-checkable, and wider than a plain token."""

from __future__ import annotations

from tests.support.entities import AccessToken, AuthCode
from xtr_security_oauth2_server_core.entities.access_token_entity_interface import (
    AccessTokenEntityInterface,
)


def test_an_access_token_entity_satisfies_the_contract() -> None:
    token: AccessTokenEntityInterface = AccessToken()
    assert isinstance(token, AccessTokenEntityInterface)


def test_a_token_that_cannot_sign_itself_does_not_satisfy_it() -> None:
    assert not isinstance(AuthCode(), AccessTokenEntityInterface)
