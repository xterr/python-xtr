"""Grant on any single grant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.authorization.voter.access import Access

from .access_decision_strategy_interface import AccessDecisionStrategyInterface

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from xtr_security_core.authorization.access_decision import AccessDecision

__all__ = ["AffirmativeStrategy"]


@final
@dataclass(frozen=True, slots=True)
class AffirmativeStrategy(AccessDecisionStrategyInterface):
    """Grants as soon as one voter grants, whatever the others say.

    The permissive default: a single grant is enough, and a denial only counts
    when nobody granted. It stops at the first grant, so the voters after it are
    never asked. When every voter abstained, the answer is
    :attr:`allow_if_all_abstain`.

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
        """Grant on the first grant, pulling no further; else deny or the abstain rule."""
        del access_decision
        denied = False
        async for result in results:
            if result is Access.GRANTED:
                return True
            if result is Access.DENIED:
                denied = True
        if denied:
            return False
        return self.allow_if_all_abstain
