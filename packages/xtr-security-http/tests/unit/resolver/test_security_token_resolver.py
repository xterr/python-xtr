"""The security token resolver reads the marker's statement against the storage."""

from __future__ import annotations

import pytest
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.exception import AuthenticationCredentialsNotFoundError
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.decorator.current_token import CurrentToken
from xtr_security_http.resolver.security_token_resolver import SecurityTokenResolver

pytestmark = pytest.mark.anyio


def _token() -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("ada", roles=["ROLE_USER"]), "api", ["ROLE_USER"])


async def test_it_returns_the_authenticated_token() -> None:
    token = _token()
    storage = TokenStorage()
    storage.set_token(token)

    assert await SecurityTokenResolver(storage).resolve(CurrentToken()) is token


async def test_it_returns_none_when_optional_and_anonymous() -> None:
    assert await SecurityTokenResolver(TokenStorage()).resolve(CurrentToken(optional=True)) is None


async def test_it_raises_when_required_and_anonymous() -> None:
    with pytest.raises(AuthenticationCredentialsNotFoundError):
        _ = await SecurityTokenResolver(TokenStorage()).resolve(CurrentToken())
