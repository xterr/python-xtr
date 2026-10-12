"""The refresh-token contract is runtime-checkable and names an access token."""

from __future__ import annotations

from tests.support.entities import AccessToken, RefreshToken
from xtr_security_oauth2_server_core.entities.refresh_token_entity_interface import (
    RefreshTokenEntityInterface,
)


def test_a_refresh_token_entity_satisfies_the_contract() -> None:
    token: RefreshTokenEntityInterface = RefreshToken()
    assert isinstance(token, RefreshTokenEntityInterface)


def test_a_token_carrying_no_access_token_does_not_satisfy_it() -> None:
    assert not isinstance(AccessToken(), RefreshTokenEntityInterface)
