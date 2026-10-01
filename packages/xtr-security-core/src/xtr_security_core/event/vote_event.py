"""The event announcing how one voter voted."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_security_core.authorization.voter.access import Access
    from xtr_security_core.authorization.voter.voter_interface import VoterInterface

__all__ = ["VoteEvent"]


@dataclass(frozen=True)
class VoteEvent(Event):
    """Announces one voter's answer, for tracing and audit.

    Dispatched by a
    :class:`~xtr_security_core.authorization.voter.traceable_voter.TraceableVoter`
    each time the voter it wraps answers, so a listener can record who voted
    what, on which attributes, over which subject, and why — without the
    decision manager knowing anything about tracing.

    Attributes:
        voter: The voter that cast the answer.
        subject: The subject the attributes concerned, or ``None``.
        attributes: The attributes voted on.
        vote: The answer the voter gave.
        reasons: The reasons the voter recorded, if any.
    """

    voter: VoterInterface
    subject: object
    attributes: Sequence[object]
    vote: Access
    reasons: tuple[str, ...] = field(default=())
