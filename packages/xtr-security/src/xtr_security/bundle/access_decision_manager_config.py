"""How the voters' answers are reduced to one decision.

Names the strategy the access-decision manager combines votes with, and the two
tie-breaking flags the strategies read. The bundle turns this into the strategy
object the manager is built with.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from xtr_security_core import (
    AccessDecisionStrategyInterface,
    AffirmativeStrategy,
    ConsensusStrategy,
    PriorityStrategy,
    UnanimousStrategy,
)

from xtr_security.exception import InvalidConfigurationError

__all__ = ["AccessDecisionManagerConfig"]

_STRATEGIES = ("affirmative", "consensus", "unanimous", "priority")


@dataclass(frozen=True, slots=True)
class AccessDecisionManagerConfig:
    """The strategy that turns the voters' answers into one grant or refusal.

    Attributes:
        strategy: How votes are combined — ``"affirmative"`` (any grant wins),
            ``"consensus"`` (the majority wins), ``"unanimous"`` (one refusal
            loses), or ``"priority"`` (the first non-abstaining voter decides).
        allow_if_all_abstain: Whether a decision every voter abstained on is
            granted.
        allow_if_equal_granted_denied: Whether a consensus tie is granted.

    Raises:
        InvalidConfigurationError: When ``strategy`` is not one of the four.
    """

    strategy: Literal["affirmative", "consensus", "unanimous", "priority"] = "affirmative"
    allow_if_all_abstain: bool = False
    allow_if_equal_granted_denied: bool = True

    def __post_init__(self) -> None:
        """Check the strategy name is one the bundle can build."""
        if self.strategy not in _STRATEGIES:
            raise InvalidConfigurationError(
                f'The strategy must be one of {list(_STRATEGIES)}, not "{self.strategy}".',
            )

    def build(self) -> AccessDecisionStrategyInterface:
        """Return the strategy object this configuration describes."""
        if self.strategy == "affirmative":
            return AffirmativeStrategy(allow_if_all_abstain=self.allow_if_all_abstain)
        if self.strategy == "unanimous":
            return UnanimousStrategy(allow_if_all_abstain=self.allow_if_all_abstain)
        if self.strategy == "priority":
            return PriorityStrategy(allow_if_all_abstain=self.allow_if_all_abstain)
        return ConsensusStrategy(
            allow_if_all_abstain=self.allow_if_all_abstain,
            allow_if_equal_granted_denied=self.allow_if_equal_granted_denied,
        )
