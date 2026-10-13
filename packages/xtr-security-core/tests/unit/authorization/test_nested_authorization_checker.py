"""The nested checker decides each check in a decision of its own and keeps its votes."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authentication.token.storage import TokenStorage
from xtr_security_core.authorization import (
    AccessDecision,
    AccessDecisionManager,
    AuthorizationChecker,
    AuthorizationCheckerInterface,
    GuestAuthorizationCheckerInterface,
    RoleVoter,
)
from xtr_security_core.authorization.nested_authorization_checker import (
    NestedAuthorizationChecker,
)
from xtr_security_core.authorization.voter import Access, Vote, VoterInterface
from xtr_security_core.exception import UnsupportedUserError
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface


@final
class _ReAuthenticatingVoter:
    """Denies, and requests a re-authentication for ``requested`` — or the attribute asked."""

    def __init__(self, requested: str | None = None) -> None:
        self._requested = requested

    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        del token, subject
        if vote is not None:
            vote.add_reason("Not recent enough.")
            asked = attributes[0]
            requested = self._requested if self._requested is not None else str(asked)
            vote.request_re_authentication(requested)
        return Access.DENIED


@final
class _UserOnlyChecker(AuthorizationCheckerInterface):
    @override
    async def is_granted(
        self,
        attribute: object,
        subject: object = None,
        access_decision: AccessDecision | None = None,
    ) -> bool:
        return True


def _checker(*voters: VoterInterface) -> AuthorizationChecker:
    storage = TokenStorage()
    storage.set_token(UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"]))
    return AuthorizationChecker(storage, AccessDecisionManager(voters))


def test_it_is_both_kinds_of_checker() -> None:
    for interface in (AuthorizationCheckerInterface, GuestAuthorizationCheckerInterface):
        assert interface in NestedAuthorizationChecker.__mro__


@pytest.mark.anyio
async def test_each_check_is_decided_in_a_record_of_its_own() -> None:
    nested = NestedAuthorizationChecker(_checker(RoleVoter()))
    vote = Vote()

    assert await nested.is_granted("ROLE_USER") is True
    assert await nested.is_granted("ROLE_ADMIN") is False

    nested.add_reasons(vote, is_granted=True)
    nested.add_reasons(vote, is_granted=False)
    assert vote.reasons == ["The user has ROLE_USER.", "The user doesn't have ROLE_ADMIN."]


@pytest.mark.anyio
async def test_a_passed_record_is_used_as_is_and_not_kept() -> None:
    nested = NestedAuthorizationChecker(_checker(RoleVoter()))
    decision = AccessDecision()
    vote = Vote()

    assert await nested.is_granted("ROLE_USER", access_decision=decision) is True

    nested.add_reasons(vote, is_granted=True)
    assert len(decision.votes) == 1
    assert vote.reasons == []


@pytest.mark.anyio
async def test_a_denial_its_own_voter_asks_to_re_authenticate_is_remembered() -> None:
    nested = NestedAuthorizationChecker(_checker(_ReAuthenticatingVoter("RECENT")))

    assert await nested.is_granted("RECENT") is False
    assert nested.re_authentication_attribute == "RECENT"


@pytest.mark.anyio
async def test_a_re_authentication_for_another_attribute_is_ignored() -> None:
    nested = NestedAuthorizationChecker(_checker(_ReAuthenticatingVoter("OTHER")))

    assert await nested.is_granted("RECENT") is False
    assert nested.re_authentication_attribute is None


@pytest.mark.anyio
async def test_only_the_first_re_authentication_is_kept() -> None:
    nested = NestedAuthorizationChecker(_checker(_ReAuthenticatingVoter()))

    _ = await nested.is_granted("FIRST")
    _ = await nested.is_granted("SECOND")

    assert nested.re_authentication_attribute == "FIRST"


@pytest.mark.anyio
async def test_is_granted_for_user_delegates_to_a_guest_checker() -> None:
    nested = NestedAuthorizationChecker(_checker(RoleVoter()))

    granted = await nested.is_granted_for_user(InMemoryUser("bob", roles=["ROLE_X"]), "ROLE_X")

    assert granted is True


@pytest.mark.anyio
async def test_is_granted_for_user_is_refused_by_a_plain_checker() -> None:
    nested = NestedAuthorizationChecker(_UserOnlyChecker())

    with pytest.raises(UnsupportedUserError, match="cannot check the access of another user"):
        _ = await nested.is_granted_for_user(None, "ROLE_X")
