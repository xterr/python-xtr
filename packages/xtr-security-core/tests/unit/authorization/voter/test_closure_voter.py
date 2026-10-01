"""The closure voter runs a callable attribute."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authorization import AccessDecisionManager
from xtr_security_core.authorization.voter import Access, ClosureVoter, RoleVoter, VoterInterface
from xtr_security_core.authorization.voter.vote import Vote
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from xtr_security_core.authorization.is_granted_context import IsGrantedContext


def test_it_inherits_the_voter_interface() -> None:
    assert VoterInterface in ClosureVoter.__mro__


def _token(*roles: str) -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", list(roles))


@pytest.mark.anyio
async def test_grants_a_sync_closure_that_returns_true() -> None:
    voter = ClosureVoter()
    _ = AccessDecisionManager([voter])

    def closure(context: IsGrantedContext, subject: object) -> bool:
        del context, subject
        return True

    assert await voter.vote(_token(), None, [closure]) is Access.GRANTED


@pytest.mark.anyio
async def test_denies_an_async_closure_that_returns_false() -> None:
    voter = ClosureVoter()
    _ = AccessDecisionManager([voter])

    async def closure(context: IsGrantedContext, subject: object) -> bool:
        del context, subject
        return False

    assert await voter.vote(_token(), None, [closure]) is Access.DENIED


@pytest.mark.anyio
async def test_the_closure_receives_the_token_and_user() -> None:
    voter = ClosureVoter()
    _ = AccessDecisionManager([voter])
    seen: dict[str, object] = {}

    def closure(context: IsGrantedContext, subject: object) -> bool:
        seen["identifier"] = context.token.get_user_identifier()
        seen["user"] = context.user
        seen["subject"] = subject
        return True

    _ = await voter.vote(_token("ROLE_USER"), "the-subject", [closure])

    assert seen["identifier"] == "alice"
    assert seen["subject"] == "the-subject"


@pytest.mark.anyio
async def test_the_closure_can_ask_a_nested_question() -> None:
    closure_voter = ClosureVoter()
    _ = AccessDecisionManager([RoleVoter(), closure_voter])

    async def closure(context: IsGrantedContext, subject: object) -> bool:
        del subject
        return await context.is_granted("ROLE_USER")

    assert await closure_voter.vote(_token("ROLE_USER"), None, [closure]) is Access.GRANTED


@pytest.mark.anyio
async def test_abstains_on_a_non_callable_attribute() -> None:
    voter = ClosureVoter()
    _ = AccessDecisionManager([voter])

    assert await voter.vote(_token(), None, ["ROLE_USER"]) is Access.ABSTAIN


@pytest.mark.anyio
async def test_an_unbound_voter_refuses_to_run() -> None:
    voter = ClosureVoter()

    def closure(context: IsGrantedContext, subject: object) -> bool:
        del context, subject
        return True

    with pytest.raises(InvalidArgumentError):
        _ = await voter.vote(_token(), None, [closure])


@pytest.mark.anyio
async def test_a_denied_closure_adds_a_reason() -> None:
    voter = ClosureVoter()
    _ = AccessDecisionManager([voter])
    vote = Vote()

    def closure(context: IsGrantedContext, subject: object) -> bool:
        del context, subject
        return False

    _ = await voter.vote(_token(), None, [closure], vote)

    assert vote.reasons


def test_binding_to_a_second_manager_is_refused() -> None:
    voter = ClosureVoter()
    _ = AccessDecisionManager([voter])

    with pytest.raises(InvalidArgumentError):
        _ = AccessDecisionManager([voter])


def test_rebinding_to_the_same_manager_is_allowed() -> None:
    voter = ClosureVoter()
    manager = AccessDecisionManager([voter])

    voter.bind_manager(manager)
