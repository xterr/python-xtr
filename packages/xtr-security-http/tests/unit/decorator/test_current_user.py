"""The CurrentUser marker resolves the current user or None."""

from __future__ import annotations

import pytest
from fastapi.params import Depends as DependsParam
from xtr_security_core.authentication.token.storage.token_storage import TokenStorage
from xtr_security_core.exception import AuthenticationCredentialsNotFoundError
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.decorator.current_user import CurrentUser

pytestmark = pytest.mark.anyio


def test_it_is_a_dependency_marker() -> None:
    assert isinstance(CurrentUser(), DependsParam)


async def test_it_returns_none_when_optional_and_anonymous() -> None:
    marker = CurrentUser(optional=True)

    assert await marker._resolve(TokenStorage()) is None


async def test_it_raises_when_required_and_anonymous() -> None:
    marker = CurrentUser()

    with pytest.raises(AuthenticationCredentialsNotFoundError):
        _ = await marker._resolve(TokenStorage())


def test_the_user_class_and_optional_flag_are_recorded() -> None:
    marker = CurrentUser(InMemoryUser, optional=True)

    assert marker.user_class is InMemoryUser
    assert marker.optional is True
