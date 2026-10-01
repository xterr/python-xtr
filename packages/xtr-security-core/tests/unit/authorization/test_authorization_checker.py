"""The authorization checker decides against the current token, or a user."""

from __future__ import annotations

import pytest

from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authentication.token.storage import TokenStorage
from xtr_security_core.authorization import (
    AccessDecisionManager,
    AuthorizationChecker,
    AuthorizationCheckerInterface,
    GuestAuthorizationCheckerInterface,
    RoleVoter,
)
from xtr_security_core.user import InMemoryUser


def test_it_inherits_both_checker_interfaces() -> None:
    for interface in (AuthorizationCheckerInterface, GuestAuthorizationCheckerInterface):
        assert interface in AuthorizationChecker.__mro__


def _checker(storage: TokenStorage) -> AuthorizationChecker:
    return AuthorizationChecker(storage, AccessDecisionManager([RoleVoter()]))


@pytest.mark.anyio
async def test_is_granted_uses_the_current_token() -> None:
    storage = TokenStorage()
    storage.set_token(UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"]))

    assert await _checker(storage).is_granted("ROLE_USER") is True


@pytest.mark.anyio
async def test_is_granted_falls_back_to_the_null_token() -> None:
    assert await _checker(TokenStorage()).is_granted("ROLE_USER") is False


@pytest.mark.anyio
async def test_is_granted_for_user_uses_the_user_roles() -> None:
    checker = _checker(TokenStorage())
    user = InMemoryUser("bob", roles=["ROLE_ADMIN"])

    assert await checker.is_granted_for_user(user, "ROLE_ADMIN") is True
    assert await checker.is_granted_for_user(user, "ROLE_OTHER") is False
