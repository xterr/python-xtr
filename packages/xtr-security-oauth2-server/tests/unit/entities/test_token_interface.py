"""The token contract is runtime-checkable against a composed token entity."""

from __future__ import annotations

from tests.support.entities import AccessToken, AuthCode, DeviceCode, Scope
from xtr_security_oauth2_server.entities.token_interface import TokenInterface


def test_an_access_token_entity_satisfies_the_contract() -> None:
    token: TokenInterface = AccessToken()
    assert isinstance(token, TokenInterface)


def test_an_auth_code_entity_satisfies_the_contract() -> None:
    code: TokenInterface = AuthCode()
    assert isinstance(code, TokenInterface)


def test_a_device_code_entity_satisfies_the_contract() -> None:
    code: TokenInterface = DeviceCode()
    assert isinstance(code, TokenInterface)


def test_an_entity_carrying_no_token_state_does_not_satisfy_it() -> None:
    assert not isinstance(Scope(), TokenInterface)
