"""The vote listener feeds a traced vote into the traceable decision manager."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from xtr_security_core import (
    Access,
    AccessDecisionManager,
    InMemoryUser,
    TraceableAccessDecisionManager,
    UsernamePasswordToken,
    VoteEvent,
)

from xtr_security.event_listener import on_vote

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core import TokenInterface, Vote

pytestmark = pytest.mark.anyio


async def test_a_vote_reaches_the_decision_being_logged() -> None:
    traceable_holder: list[TraceableAccessDecisionManager] = []

    @final
    class _Announcing:
        async def vote(
            self,
            token: TokenInterface,
            subject: object,
            attributes: Sequence[object],
            vote: Vote | None = None,
        ) -> Access:
            del token, vote
            event = VoteEvent(
                voter=self,
                subject=subject,
                attributes=tuple(attributes),
                vote=Access.GRANTED,
                reasons=("because",),
            )
            await on_vote(event, traceable_holder[0])
            return Access.GRANTED

    voter = _Announcing()
    traceable = TraceableAccessDecisionManager(AccessDecisionManager([voter]))
    traceable_holder.append(traceable)

    _ = await traceable.decide(
        UsernamePasswordToken(InMemoryUser("alice"), "api"), ["ANY"], "subject"
    )

    (entry,) = traceable.get_decision_log()
    assert entry["voter_details"] == [
        {"voter": voter, "attributes": ("ANY",), "vote": Access.GRANTED, "reasons": ("because",)},
    ]
