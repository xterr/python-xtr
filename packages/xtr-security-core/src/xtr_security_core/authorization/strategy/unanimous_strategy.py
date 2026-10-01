"""Grant only when no voter denies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.authorization.voter.access import Access

from .access_decision_strategy_interface import AccessDecisionStrategyInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_security_core.authorization.access_decision import AccessDecision

__all__ = ["UnanimousStrategy"]


@final
@dataclass(frozen=True, slots=True)
class UnanimousStrategy(AccessDecisionStrategyInterface):
    """Grants only when not one voter denies.

    The strict one: a single denial refuses, however many voters granted, and it
    stops at the first denial without asking the rest. It grants when at least
    one voter granted and none denied, and falls back to
    :attr:`allow_if_all_abstain` when every voter abstained.

    Attributes:
        allow_if_all_abstain: What to answer when no voter had an opinion.
    """

    allow_if_all_abstain: bool = False

    @override
    async def decide(
        self,
        results: AsyncIterator[Access],
        access_decision: AccessDecision | None = None,
    ) -> bool:
        """Refuse on the first denial; grant on a grant; else fall to the abstain rule."""
        del access_decision
        granted = 0
        async for result in results:
            if result is Access.DENIED:
                return False
            if result is Access.GRANTED:
                granted += 1
        if granted > 0:
            return True
        return self.allow_if_all_abstain
