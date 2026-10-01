"""The access-decision-manager configuration builds the strategy it names."""

from __future__ import annotations

import pytest
from xtr_security_core import (
    AffirmativeStrategy,
    ConsensusStrategy,
    PriorityStrategy,
    UnanimousStrategy,
)

from xtr_security.bundle import AccessDecisionManagerConfig
from xtr_security.exception import InvalidConfigurationError


@pytest.mark.parametrize(
    ("strategy", "expected"),
    [
        ("affirmative", AffirmativeStrategy),
        ("consensus", ConsensusStrategy),
        ("unanimous", UnanimousStrategy),
        ("priority", PriorityStrategy),
    ],
)
def test_it_builds_the_named_strategy(strategy: str, expected: type) -> None:
    config = AccessDecisionManagerConfig(strategy=strategy)  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # exercised through the parametrize

    assert isinstance(config.build(), expected)


def test_an_unknown_strategy_is_refused() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = AccessDecisionManagerConfig(strategy="majority")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]  # the point of the test


def test_consensus_carries_its_tie_break() -> None:
    config = AccessDecisionManagerConfig(
        strategy="consensus",
        allow_if_equal_granted_denied=False,
    )
    strategy = config.build()

    assert isinstance(strategy, ConsensusStrategy)
    assert strategy.allow_if_equal_granted_denied is False
