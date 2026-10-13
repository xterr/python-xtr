"""The closure voter runs a callable attribute."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_security_core.authentication import AuthenticationTrustResolver
from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authorization import AccessDecisionManager
from xtr_security_core.authorization.voter import (
    Access,
    AuthenticatedVoter,
    CacheableVoterInterface,
    ClosureVoter,
    RoleVoter,
    VoterInterface,
)
from xtr_security_core.authorization.voter.vote import Vote
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from xtr_security_core.authorization.is_granted_context import IsGrantedContext


def test_it_inherits_the_cacheable_voter_interface() -> None:
    assert CacheableVoterInterface in ClosureVoter.__mro__


def test_it_never_supports_a_string_attribute_but_any_type() -> None:
    voter = ClosureVoter()

    assert voter.supports_attribute("ROLE_USER") is False
    assert voter.supports_type("anything") is True


def _token(*roles: str) -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", list(roles))


def _bound(*voters: VoterInterface) -> ClosureVoter:
    voter = ClosureVoter()
    _ = AccessDecisionManager([*voters, voter])
    return voter


def allow(context: IsGrantedContext, subject: object) -> bool:
    del context, subject
    return True


def refuse(context: IsGrantedContext, subject: object) -> bool:
    del context, subject
    return False


def other_refusal(context: IsGrantedContext, subject: object) -> bool:
    del context, subject
    return False


@pytest.mark.anyio
async def test_grants_a_sync_closure_that_returns_true() -> None:
    assert await _bound().vote(_token(), None, [allow]) is Access.GRANTED


@pytest.mark.anyio
async def test_denies_an_async_closure_that_returns_false() -> None:
    async def closure(context: IsGrantedContext, subject: object) -> bool:
        del context, subject
        return False

    assert await _bound().vote(_token(), None, [closure]) is Access.DENIED


@pytest.mark.anyio
async def test_the_closure_receives_the_token_user_and_subject() -> None:
    seen: dict[str, object] = {}
    token = _token("ROLE_USER")

    def closure(context: IsGrantedContext, subject: object) -> bool:
        seen["token"] = context.token
        seen["user"] = context.user
        seen["subject"] = subject
        return True

    _ = await _bound().vote(token, "the-subject", [closure])

    assert seen == {"token": token, "user": token.get_user(), "subject": "the-subject"}


@pytest.mark.anyio
async def test_the_closure_can_ask_a_nested_question_for_the_same_token() -> None:
    async def closure(context: IsGrantedContext, subject: object) -> bool:
        del subject
        return await context.is_granted("ROLE_USER")

    voter = _bound(RoleVoter())

    assert await voter.vote(_token("ROLE_USER"), None, [closure]) is Access.GRANTED
    assert await voter.vote(_token("ROLE_OTHER"), None, [closure]) is Access.DENIED


@pytest.mark.anyio
async def test_abstains_on_a_non_callable_attribute() -> None:
    assert await _bound().vote(_token(), None, ["ROLE_USER"]) is Access.ABSTAIN


@pytest.mark.anyio
async def test_an_unbound_voter_refuses_to_run() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = await ClosureVoter().vote(_token(), None, [allow])


@pytest.mark.anyio
async def test_a_granting_closure_reports_its_name_and_the_granting_reasons() -> None:
    async def closure(context: IsGrantedContext, subject: object) -> bool:
        del subject
        return await context.is_granted("ROLE_USER")

    vote = Vote()

    _ = await _bound(RoleVoter()).vote(_token("ROLE_USER"), None, [closure], vote)

    assert vote.reasons == ["The user has ROLE_USER.", "Closure closure returned true."]


@pytest.mark.anyio
async def test_a_refusing_closure_reports_its_name_and_the_denying_reasons() -> None:
    async def closure(context: IsGrantedContext, subject: object) -> bool:
        del subject
        return await context.is_granted("ROLE_ADMIN")

    vote = Vote()

    _ = await _bound(RoleVoter()).vote(_token("ROLE_USER"), None, [closure], vote)

    assert vote.reasons == ["The user doesn't have ROLE_ADMIN.", "Closure closure returned false."]


@pytest.mark.anyio
async def test_several_refusing_closures_are_named_together() -> None:
    vote = Vote()

    result = await _bound().vote(_token(), None, [refuse, other_refusal], vote)

    assert result is Access.DENIED
    assert vote.reasons == ["Closures refuse, other_refusal returned false."]


@pytest.mark.anyio
async def test_a_denied_recency_check_requests_a_re_authentication() -> None:
    async def closure(context: IsGrantedContext, subject: object) -> bool:
        del subject
        return await context.is_authenticated_recently()

    vote = Vote()
    voter = _bound(AuthenticatedVoter(AuthenticationTrustResolver()))

    result = await voter.vote(_token("ROLE_USER"), None, [closure], vote)

    assert result is Access.DENIED
    assert vote.re_authentication_attribute == AuthenticatedVoter.IS_AUTHENTICATED_RECENTLY


@pytest.mark.anyio
async def test_a_callable_object_is_named_by_its_type() -> None:
    class Check:
        def __call__(self, context: IsGrantedContext, subject: object) -> bool:
            del context, subject
            return False

    vote = Vote()

    _ = await _bound().vote(_token(), None, [Check()], vote)

    assert vote.reasons == ["Closure Check returned false."]


def test_binding_to_a_second_manager_is_refused() -> None:
    voter = ClosureVoter()
    _ = AccessDecisionManager([voter])

    with pytest.raises(InvalidArgumentError):
        _ = AccessDecisionManager([voter])


def test_rebinding_to_the_same_manager_is_allowed() -> None:
    voter = ClosureVoter()
    manager = AccessDecisionManager([voter])

    voter.bind_manager(manager)
