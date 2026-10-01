"""The strategy interface is a runtime-checkable structural protocol."""

from __future__ import annotations

from xtr_security_core.authorization import (
    AccessDecisionStrategyInterface,
    AffirmativeStrategy,
    ConsensusStrategy,
    PriorityStrategy,
    UnanimousStrategy,
)


def test_every_strategy_satisfies_the_interface() -> None:
    for strategy in (
        AffirmativeStrategy(),
        ConsensusStrategy(),
        PriorityStrategy(),
        UnanimousStrategy(),
    ):
        assert isinstance(strategy, AccessDecisionStrategyInterface)


def test_an_object_without_decide_does_not_satisfy_it() -> None:
    assert not isinstance(object(), AccessDecisionStrategyInterface)
