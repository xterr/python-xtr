"""The CurrentUser marker records its metadata and delegates resolution."""

from __future__ import annotations

import pytest
from fastapi.params import Depends as DependsParam
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.authentication.token.username_password_token import UsernamePasswordToken
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.decorator.current_user import CurrentUser
from xtr_security_http.resolver.user_value_resolver import UserValueResolver

pytestmark = pytest.mark.anyio


def test_it_is_a_dependency_marker() -> None:
    assert isinstance(CurrentUser(), DependsParam)


def test_it_records_its_flags() -> None:
    marker = CurrentUser(InMemoryUser, optional=True, disabled=True)

    assert marker.user_class is InMemoryUser
    assert marker.optional is True
    assert marker.disabled is True


async def test_it_resolves_the_authenticated_user_through_the_resolver() -> None:
    user = InMemoryUser("ada", roles=["ROLE_USER"])
    storage = TokenStorage()
    storage.set_token(UsernamePasswordToken(user, "api", ["ROLE_USER"]))
    marker = CurrentUser()

    assert await marker._resolve(UserValueResolver(storage)) is user


async def test_disabled_yields_none_without_reading_the_request() -> None:
    """``disabled`` switches the resolution off where the resolver is enabled."""
    marker = CurrentUser(disabled=True)

    assert await marker._resolve(UserValueResolver(TokenStorage())) is None
