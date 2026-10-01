"""The strategies that reduce a set of votes to one decision."""

from __future__ import annotations

from .access_decision_strategy_interface import AccessDecisionStrategyInterface
from .affirmative_strategy import AffirmativeStrategy
from .consensus_strategy import ConsensusStrategy
from .priority_strategy import PriorityStrategy
from .unanimous_strategy import UnanimousStrategy

__all__ = [
    "AccessDecisionStrategyInterface",
    "AffirmativeStrategy",
    "ConsensusStrategy",
    "PriorityStrategy",
    "UnanimousStrategy",
]
