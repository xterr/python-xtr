"""The record of one access decision: its votes and its outcome."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .voter.access import Access

if TYPE_CHECKING:
    from .voter.vote import Vote

__all__ = ["AccessDecision"]


@dataclass(slots=True)
class AccessDecision:
    """What was decided, by which strategy, and every vote behind it.

    A decision is not only a yes or no: it is the votes that produced it. The
    manager fills one of these as the voters answer, so a refusal can be
    explained — the :attr:`message` reads the denying voters' reasons. A nested
    decision made while one is in progress shares the same record, so its votes
    are gathered here too.

    Attributes:
        is_granted: The outcome, once the manager has decided.
        votes: Every vote cast, in the order they were cast.
        strategy: The name of the strategy that decided, once set.
    """

    is_granted: bool = False
    votes: list[Vote] = field(default_factory=list)
    strategy: str | None = None

    @property
    def message(self) -> str:
        """A short account of the decision: granted, or why it was denied."""
        if self.is_granted:
            return "Access granted."
        reasons = [
            reason for vote in self.votes if vote.result is Access.DENIED for reason in vote.reasons
        ]
        if reasons:
            return "Access denied. " + " ".join(reasons)
        return "Access denied."
