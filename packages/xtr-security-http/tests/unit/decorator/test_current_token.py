"""The CurrentToken marker records its metadata and delegates resolution."""

from __future__ import annotations

import pytest
from fastapi.params import Depends as DependsParam
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.decorator.current_token import CurrentToken
from xtr_security_http.resolver.security_token_resolver import SecurityTokenResolver

pytestmark = pytest.mark.anyio


def test_it_is_a_dependency_marker() -> None:
    assert isinstance(CurrentToken(), DependsParam)


def test_it_records_its_flags() -> None:
    marker = CurrentToken(optional=True)

    assert marker.optional is True


async def test_it_resolves_the_authenticated_token_through_the_resolver() -> None:
    token = UsernamePasswordToken(InMemoryUser("ada", roles=["ROLE_USER"]), "api", ["ROLE_USER"])
    storage = TokenStorage()
    storage.set_token(token)

    assert await CurrentToken()._resolve(SecurityTokenResolver(storage)) is token
