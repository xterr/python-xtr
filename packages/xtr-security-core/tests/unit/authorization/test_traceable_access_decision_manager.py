"""The traceable manager logs every decision, its votes and its strategy."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from xtr_security_core.authentication.token import UsernamePasswordToken
from xtr_security_core.authorization import (
    AccessDecision,
    AccessDecisionManager,
    AccessDecisionManagerInterface,
    RoleVoter,
    TraceableAccessDecisionManager,
)
from xtr_security_core.authorization.voter import Access
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.authorization.voter import Vote


def _token() -> UsernamePasswordToken:
    return UsernamePasswordToken(InMemoryUser("alice"), "api", ["ROLE_USER"])


@final
class _ReportingVoter:
    """A role voter that reports its vote to a traceable manager, as a listener would."""

    def __init__(self) -> None:
        self.traceable: TraceableAccessDecisionManager | None = None
        self._role_voter = RoleVoter()

    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        result = await self._role_voter.vote(token, subject, attributes, vote)
        if self.traceable is not None:
            self.traceable.add_voter_vote(self, attributes, result, ["a reason"])
        return result


def test_it_is_a_decision_manager() -> None:
    assert AccessDecisionManagerInterface in TraceableAccessDecisionManager.__mro__


@pytest.mark.anyio
async def test_it_decides_through_the_decorated_manager_and_logs_it() -> None:
    voter = _ReportingVoter()
    traceable = TraceableAccessDecisionManager(AccessDecisionManager([voter]))
    voter.traceable = traceable

    granted = await traceable.decide(_token(), ["ROLE_USER"], "subject")

    assert granted is True
    assert traceable.get_strategy() == "affirmative"
    assert traceable.get_voters() == (voter,)
    assert traceable.get_decision_log() == (
        {
            "attributes": ("ROLE_USER",),
            "object": "subject",
            "voter_details": [
                {
                    "voter": voter,
                    "attributes": ("ROLE_USER",),
                    "vote": Access.GRANTED,
                    "reasons": ("a reason",),
                },
            ],
            "result": True,
        },
    )


@pytest.mark.anyio
async def test_a_passed_decision_is_filled() -> None:
    traceable = TraceableAccessDecisionManager(AccessDecisionManager([RoleVoter()]))
    decision = AccessDecision()

    _ = await traceable.decide(_token(), ["ROLE_ADMIN"], access_decision=decision)

    assert decision.is_granted is False
    assert decision.strategy == "affirmative"
    assert len(decision.votes) == 1


@pytest.mark.anyio
async def test_a_failed_decision_is_logged_without_a_result() -> None:
    traceable = TraceableAccessDecisionManager(AccessDecisionManager([RoleVoter()]))

    with pytest.raises(InvalidArgumentError):
        _ = await traceable.decide(_token(), ["ROLE_A", "ROLE_B"])

    (entry,) = traceable.get_decision_log()
    assert "result" not in entry


def test_a_vote_outside_any_decision_is_ignored() -> None:
    traceable = TraceableAccessDecisionManager(AccessDecisionManager())

    traceable.add_voter_vote(RoleVoter(), ["ROLE_USER"], Access.GRANTED)

    assert traceable.get_voters() == ()
    assert traceable.get_decision_log() == ()


def test_the_strategy_is_unknown_before_any_decision() -> None:
    assert TraceableAccessDecisionManager(AccessDecisionManager()).get_strategy() == "-"


@pytest.mark.anyio
async def test_reset_forgets_everything() -> None:
    voter = _ReportingVoter()
    traceable = TraceableAccessDecisionManager(AccessDecisionManager([voter]))
    voter.traceable = traceable
    _ = await traceable.decide(_token(), ["ROLE_USER"])

    traceable.reset()

    assert traceable.get_strategy() == "-"
    assert traceable.get_voters() == ()
    assert traceable.get_decision_log() == ()


@pytest.mark.anyio
async def test_a_decision_asked_during_one_is_logged_and_joins_its_record() -> None:
    traceable_holder: list[TraceableAccessDecisionManager] = []

    @final
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
            granted = await traceable_holder[0].decide(token, ["ROLE_USER"])
            return Access.GRANTED if granted else Access.DENIED

    traceable = TraceableAccessDecisionManager(AccessDecisionManager([RoleVoter(), _Asking()]))
    traceable_holder.append(traceable)
    decision = AccessDecision()

    assert await traceable.decide(_token(), ["OUTER"], access_decision=decision) is True

    log = traceable.get_decision_log()
    assert [entry["attributes"] for entry in log] == [("ROLE_USER",), ("OUTER",)]
    # The nested decision's grant — affirmative stops there — then the asking voter's own.
    assert len(decision.votes) == 2
