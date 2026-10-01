"""The traceable voter announces every vote it passes through."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from typing_extensions import override

from tests.support.dispatchers import RecordingDispatcher
from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authorization import (
    AccessDecision,
    AccessDecisionManager,
    ClosureVoter,
    RoleVoter,
)
from xtr_security_core.authorization.voter import (
    Access,
    CacheableVoterInterface,
    TraceableVoter,
    VoterInterface,
)
from xtr_security_core.event import VoteEvent
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.is_granted_context import IsGrantedContext
    from xtr_security_core.authorization.voter import Vote


@final
class PlainVoter(VoterInterface):
    """A voter that is not cacheable, for the fall-back branch."""

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        del token, subject, attributes, vote
        return Access.ABSTAIN


def test_it_inherits_the_cacheable_voter_interface() -> None:
    assert CacheableVoterInterface in TraceableVoter.__mro__


def _token(*roles: str) -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", list(roles))


def _only_vote_event(dispatcher: RecordingDispatcher) -> VoteEvent:
    assert len(dispatcher.events) == 1
    event = dispatcher.events[0]
    assert isinstance(event, VoteEvent)
    return event


@pytest.mark.anyio
async def test_delegates_the_vote_and_returns_its_result() -> None:
    voter = TraceableVoter(RoleVoter(), RecordingDispatcher())

    result = await voter.vote(_token("ROLE_USER"), None, ["ROLE_USER"])

    assert result is Access.GRANTED


@pytest.mark.anyio
async def test_announces_a_vote_event_with_the_result_and_reasons() -> None:
    dispatcher = RecordingDispatcher()
    inner = RoleVoter()
    voter = TraceableVoter(inner, dispatcher)

    _ = await voter.vote(_token("ROLE_USER"), "book", ["ROLE_ADMIN"])

    event = _only_vote_event(dispatcher)
    assert event.voter is inner
    assert event.subject == "book"
    assert event.attributes == ("ROLE_ADMIN",)
    assert event.vote is Access.DENIED
    assert event.reasons


@pytest.mark.anyio
async def test_creates_a_vote_record_when_none_is_passed() -> None:
    dispatcher = RecordingDispatcher()
    voter = TraceableVoter(RoleVoter(), dispatcher)

    _ = await voter.vote(_token("ROLE_USER"), None, ["ROLE_ADMIN"], None)

    assert _only_vote_event(dispatcher).reasons


def test_supports_follow_a_cacheable_inner_voter() -> None:
    voter = TraceableVoter(RoleVoter(prefix="ROLE_"), RecordingDispatcher())

    assert voter.supports_attribute("ROLE_X") is True
    assert voter.supports_attribute("OTHER") is False
    assert voter.supports_type("anything") is True


def test_supports_say_yes_for_a_non_cacheable_inner_voter() -> None:
    voter = TraceableVoter(PlainVoter(), RecordingDispatcher())

    assert not isinstance(PlainVoter(), CacheableVoterInterface)
    assert voter.supports_attribute("anything") is True
    assert voter.supports_type("anything") is True


def test_get_decorated_voter_returns_the_wrapped_one() -> None:
    inner = RoleVoter()

    assert TraceableVoter(inner, RecordingDispatcher()).get_decorated_voter() is inner


@pytest.mark.anyio
async def test_the_recorded_vote_names_the_unwrapped_voter() -> None:
    inner = RoleVoter()
    traced = TraceableVoter(inner, RecordingDispatcher())
    manager = AccessDecisionManager([traced])

    decision = AccessDecision()
    _ = await manager.decide(_token("ROLE_USER"), ["ROLE_USER"], access_decision=decision)

    assert decision.votes[0].voter is inner


@pytest.mark.anyio
async def test_the_manager_binds_a_closure_voter_through_the_trace() -> None:
    dispatcher = RecordingDispatcher()
    closure_voter = ClosureVoter()
    traced = TraceableVoter(closure_voter, dispatcher)
    manager = AccessDecisionManager([RoleVoter(), traced])

    async def closure(context: IsGrantedContext, subject: object) -> bool:
        del subject
        return await context.is_granted("ROLE_USER")

    decision = AccessDecision()
    granted = await manager.decide(_token("ROLE_USER"), [closure], access_decision=decision)

    assert granted is True
    assert any(isinstance(event, VoteEvent) for event in dispatcher.events)
