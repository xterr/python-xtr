"""What turns a set of votes into one yes-or-no answer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_security_core.authorization.access_decision import AccessDecision
    from xtr_security_core.authorization.voter.access import Access

__all__ = ["AccessDecisionStrategyInterface"]


@runtime_checkable
class AccessDecisionStrategyInterface(Protocol):
    """Reduces the voters' answers to a single decision.

    The voters each granted, denied or abstained; a strategy says what the
    collection of those answers means — whether one grant is enough, whether a
    single denial is fatal, what to do when they all abstain or split evenly.

    The answers arrive lazily: ``results`` is an async iterator that runs the
    next applicable voter only when the strategy pulls from it, so a strategy
    that can settle early leaves the voters it never reaches unasked.
    """

    async def decide(
        self,
        results: AsyncIterator[Access],
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Return whether access is granted given the voters' ``results``."""
        ...
