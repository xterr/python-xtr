"""Let the first voter with an opinion decide."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.authorization.voter.access import Access

from .access_decision_strategy_interface import AccessDecisionStrategyInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_security_core.authorization.access_decision import AccessDecision

__all__ = ["PriorityStrategy"]


@final
@dataclass(frozen=True, slots=True)
class PriorityStrategy(AccessDecisionStrategyInterface):
    """Grants or denies on the first voter that does not abstain.

    Order is everything: the voters are asked in the order they were given, and
    the first one to grant or deny settles it — the rest are never consulted,
    because the strategy stops pulling from the voters the moment one has an
    opinion. When all of them abstain, the answer is :attr:`allow_if_all_abstain`.

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
        """Answer on the first non-abstaining result, pulling no further; else the abstain rule."""
        del access_decision
        async for result in results:
            if result is Access.GRANTED:
                return True
            if result is Access.DENIED:
                return False
        return self.allow_if_all_abstain
