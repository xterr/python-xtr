"""Feeds every traced vote into the request's traceable decision manager."""

from __future__ import annotations

# The dispatcher reads the listener's signature at runtime to find its event
# and to fill the manager from the container, so both stay importable here.
from xtr_dependency_injection import Injected  # noqa: TC002
from xtr_event_dispatcher import as_event_listener
from xtr_security_core.authorization.traceable_access_decision_manager import (  # noqa: TC002
    TraceableAccessDecisionManager,
)
from xtr_security_core.event.vote_event import VoteEvent  # noqa: TC002

__all__ = ["on_vote"]


@as_event_listener()
async def on_vote(event: VoteEvent, manager: Injected[TraceableAccessDecisionManager]) -> None:
    """Record the vote on the decision the request's traceable manager is logging.

    The manager is scoped to the request, so it is filled on every call, from
    the unit of work the vote was cast in.
    """
    manager.add_voter_vote(event.voter, event.attributes, event.vote, event.reasons)
