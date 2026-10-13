"""The authorization checker decides against the current token, or a given user."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_security_core.authentication import AuthenticationTrustResolver
from xtr_security_core.authentication.token import AbstractToken, UsernamePasswordToken
from xtr_security_core.authentication.token.offline_token_interface import OfflineTokenInterface
from xtr_security_core.authentication.token.storage import TokenStorage
from xtr_security_core.authorization import (
    AccessDecision,
    AccessDecisionManager,
    AuthenticatedVoter,
    AuthorizationChecker,
    AuthorizationCheckerInterface,
    GuestAuthorizationCheckerInterface,
    RoleVoter,
    UserAuthorizationCheckerInterface,
)
from xtr_security_core.authorization.voter import Access
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.voter import Vote


def test_it_inherits_every_checker_interface() -> None:
    for interface in (
        AuthorizationCheckerInterface,
        GuestAuthorizationCheckerInterface,
        UserAuthorizationCheckerInterface,
    ):
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
async def test_a_token_without_a_user_is_replaced_by_the_null_token() -> None:
    storage = TokenStorage()
    storage.set_token(AbstractToken(["ROLE_USER"]))

    assert await _checker(storage).is_granted("ROLE_USER") is False


@pytest.mark.anyio
async def test_a_passed_decision_is_filled() -> None:
    storage = TokenStorage()
    storage.set_token(UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"]))
    decision = AccessDecision()

    _ = await _checker(storage).is_granted("ROLE_USER", access_decision=decision)

    assert decision.is_granted is True


@pytest.mark.anyio
async def test_is_granted_for_user_uses_the_user_roles() -> None:
    checker = _checker(TokenStorage())
    user = InMemoryUser("bob", roles=["ROLE_ADMIN"])

    assert await checker.is_granted_for_user(user, "ROLE_ADMIN") is True
    assert await checker.is_granted_for_user(user, "ROLE_OTHER") is False


@pytest.mark.anyio
async def test_is_granted_for_a_guest_has_no_roles() -> None:
    checker = _checker(TokenStorage())

    assert await checker.is_granted_for_user(None, "ROLE_USER") is False


@pytest.mark.anyio
async def test_authentication_attributes_for_a_given_user_are_refused() -> None:
    manager = AccessDecisionManager([AuthenticatedVoter(AuthenticationTrustResolver())])
    checker = AuthorizationChecker(TokenStorage(), manager)
    user = InMemoryUser("bob", roles=["ROLE_ADMIN"])

    with pytest.raises(InvalidArgumentError, match="offline token"):
        _ = await checker.is_granted_for_user(user, AuthenticatedVoter.IS_AUTHENTICATED)


@pytest.mark.anyio
async def test_a_guest_is_not_authenticated() -> None:
    manager = AccessDecisionManager([AuthenticatedVoter(AuthenticationTrustResolver())])
    checker = AuthorizationChecker(TokenStorage(), manager)

    assert await checker.is_granted_for_user(None, AuthenticatedVoter.IS_AUTHENTICATED) is False


@pytest.mark.anyio
async def test_a_voter_asking_the_checker_sees_the_offline_token() -> None:
    storage = TokenStorage()
    storage.set_token(UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"]))
    checkers: list[AuthorizationChecker] = []
    seen: list[TokenInterface] = []

    class _Asking:
        async def vote(
            self,
            token: TokenInterface,
            subject: object,
            attributes: Sequence[object],
            vote: Vote | None = None,
        ) -> Access:
            del subject, vote
            if list(attributes) != ["OUTER"]:
                return Access.ABSTAIN
            seen.append(token)
            granted = await checkers[0].is_granted("ROLE_ADMIN")
            return Access.GRANTED if granted else Access.DENIED

    checker = AuthorizationChecker(storage, AccessDecisionManager([RoleVoter(), _Asking()]))
    checkers.append(checker)
    bob = InMemoryUser("bob", roles=["ROLE_ADMIN"])

    assert await checker.is_granted("OUTER") is False
    assert await checker.is_granted_for_user(bob, "OUTER") is True
    assert OfflineTokenInterface not in type(seen[0]).__mro__
    assert OfflineTokenInterface in type(seen[1]).__mro__


@pytest.mark.anyio
async def test_another_checker_does_not_see_the_offline_token() -> None:
    storage = TokenStorage()
    storage.set_token(UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"]))
    other = _checker(storage)
    granted_inside: list[bool] = []

    class _Asking:
        async def vote(
            self,
            token: TokenInterface,
            subject: object,
            attributes: Sequence[object],
            vote: Vote | None = None,
        ) -> Access:
            del token, subject, attributes, vote
            granted_inside.append(await other.is_granted("ROLE_ADMIN"))
            return Access.ABSTAIN

    checker = AuthorizationChecker(storage, AccessDecisionManager([_Asking()]))

    _ = await checker.is_granted_for_user(InMemoryUser("bob", roles=["ROLE_ADMIN"]), "ANY")

    assert granted_inside == [False]


@pytest.mark.anyio
async def test_the_offline_token_is_dropped_once_the_decision_ends() -> None:
    checker = _checker(TokenStorage())

    _ = await checker.is_granted_for_user(InMemoryUser("bob", roles=["ROLE_ADMIN"]), "ROLE_ADMIN")

    assert await checker.is_granted("ROLE_ADMIN") is False
