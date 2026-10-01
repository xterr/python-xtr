"""A voter that records every vote it passes through."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.event.vote_event import VoteEvent

from .cacheable_voter_interface import CacheableVoterInterface
from .vote import Vote

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_event_dispatcher_contracts import EventDispatcherInterface

    from xtr_security_core.authentication.token.token_interface import TokenInterface

    from .access import Access
    from .voter_interface import VoterInterface

__all__ = ["TraceableVoter"]


@final
class TraceableVoter(CacheableVoterInterface):
    """Wraps a voter and announces each answer as a :class:`VoteEvent`.

    A transparent decoration: it delegates every vote to the voter it wraps,
    then dispatches an event carrying the answer and the reasons behind it, so
    a decision can be traced without the decision manager or the wrapped voter
    knowing tracing exists. Its applicability declarations follow the wrapped
    voter's when that voter is cacheable, and otherwise say yes to everything.
    """

    __slots__ = ("_event_dispatcher", "_voter")

    _voter: VoterInterface
    _event_dispatcher: EventDispatcherInterface

    def __init__(self, voter: VoterInterface, event_dispatcher: EventDispatcherInterface) -> None:
        """Record the voter to trace and the dispatcher to announce votes on."""
        self._voter = voter
        self._event_dispatcher = event_dispatcher

    @override
    async def vote(
        self,
        token: TokenInterface,
        subject: object,
        attributes: Sequence[object],
        vote: Vote | None = None,
    ) -> Access:
        """Delegate the vote, then announce the answer and its reasons."""
        record = vote if vote is not None else Vote()
        result = await self._voter.vote(token, subject, attributes, record)
        record.result = result
        _ = await self._event_dispatcher.dispatch(
            VoteEvent(
                voter=self._voter,
                subject=subject,
                attributes=tuple(attributes),
                vote=result,
                reasons=tuple(record.reasons),
            ),
        )
        return result

    @override
    def supports_attribute(self, attribute: str) -> bool:
        """Follow the wrapped voter when it is cacheable, else say yes."""
        if isinstance(self._voter, CacheableVoterInterface):
            return self._voter.supports_attribute(attribute)
        return True

    @override
    def supports_type(self, subject_type: str) -> bool:
        """Follow the wrapped voter when it is cacheable, else say yes."""
        if isinstance(self._voter, CacheableVoterInterface):
            return self._voter.supports_type(subject_type)
        return True

    def get_decorated_voter(self) -> VoterInterface:
        """Return the voter this one wraps."""
        return self._voter
