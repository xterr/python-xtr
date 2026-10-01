"""The security facade answers who is calling, and what they may do."""

from __future__ import annotations

from typing import final

import pytest
from xtr_security_core import (
    AccessDecisionManager,
    AuthorizationChecker,
    AuthorizationCheckerInterface,
    GuestAuthorizationCheckerInterface,
    InMemoryUser,
    RoleVoter,
    TokenStorage,
    UsernamePasswordToken,
)
from xtr_security_core.exception import AccessDeniedError, UnsupportedUserError

from xtr_security import Security


def test_it_inherits_both_checker_interfaces() -> None:
    for interface in (AuthorizationCheckerInterface, GuestAuthorizationCheckerInterface):
        assert interface in Security.__mro__


def _security(storage: TokenStorage) -> Security:
    checker = AuthorizationChecker(storage, AccessDecisionManager([RoleVoter()]))
    return Security(storage, checker)


def _authenticated() -> TokenStorage:
    storage = TokenStorage()
    storage.set_token(UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"]))
    return storage


def test_get_token_and_user_when_anonymous() -> None:
    security = _security(TokenStorage())

    assert security.get_token() is None
    assert security.get_user() is None


def test_get_token_and_user_when_authenticated() -> None:
    security = _security(_authenticated())

    assert security.get_token() is not None
    user = security.get_user()
    assert user is not None
    assert user.get_user_identifier() == "alice"


@pytest.mark.anyio
async def test_is_granted() -> None:
    security = _security(_authenticated())

    assert await security.is_granted("ROLE_USER") is True
    assert await security.is_granted("ROLE_ADMIN") is False


@pytest.mark.anyio
async def test_is_granted_for_user() -> None:
    security = _security(TokenStorage())
    user = InMemoryUser("bob", roles=["ROLE_ADMIN"])

    assert await security.is_granted_for_user(user, "ROLE_ADMIN") is True


@pytest.mark.anyio
async def test_is_granted_for_user_refused_without_a_guest_checker() -> None:
    @final
    class OnlyCurrent:
        async def is_granted(
            self,
            attribute: object,
            subject: object = None,
            access_decision: object = None,
        ) -> bool:
            del attribute, subject, access_decision
            return True

    security = Security(TokenStorage(), OnlyCurrent())

    with pytest.raises(UnsupportedUserError):
        _ = await security.is_granted_for_user(InMemoryUser("bob"), "ROLE_USER")


@pytest.mark.anyio
async def test_deny_access_unless_granted_passes_silently() -> None:
    security = _security(_authenticated())

    await security.deny_access_unless_granted("ROLE_USER")


@pytest.mark.anyio
async def test_deny_access_unless_granted_raises_with_the_decision() -> None:
    security = _security(_authenticated())

    with pytest.raises(AccessDeniedError) as caught:
        await security.deny_access_unless_granted("ROLE_ADMIN", message="nope")

    error = caught.value
    assert error.attributes == ("ROLE_ADMIN",)
    assert error.access_decision is not None
    assert error.access_decision.is_granted is False
    assert error.access_decision.strategy == "AffirmativeStrategy"
