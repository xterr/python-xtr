"""Grant when more voters grant than deny."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.authorization.voter.access import Access

from .access_decision_strategy_interface import AccessDecisionStrategyInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_security_core.authorization.access_decision import AccessDecision

__all__ = ["ConsensusStrategy"]


@final
@dataclass(frozen=True, slots=True)
class ConsensusStrategy(AccessDecisionStrategyInterface):
    """Grants when grants outnumber denials, and vice versa.

    The majority rules, so every voter is asked: the tally is only complete once
    the last one has answered. A tie between grants and denials is broken by
    :attr:`allow_if_equal_granted_denied`; a vote in which everyone abstained
    is decided by :attr:`allow_if_all_abstain`.

    Attributes:
        allow_if_all_abstain: What to answer when no voter had an opinion.
        allow_if_equal_granted_denied: What to answer on a grant/deny tie.
    """

    allow_if_all_abstain: bool = False
    allow_if_equal_granted_denied: bool = True

    @override
    async def decide(
        self,
        results: AsyncIterator[Access],
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Compare grants to denials, breaking a tie and an all-abstain by the flags."""
        del access_decision
        granted = 0
        denied = 0
        async for result in results:
            if result is Access.GRANTED:
                granted += 1
            elif result is Access.DENIED:
                denied += 1
        if granted > denied:
            return True
        if denied > granted:
            return False
        if granted > 0:
            return self.allow_if_equal_granted_denied
        return self.allow_if_all_abstain
