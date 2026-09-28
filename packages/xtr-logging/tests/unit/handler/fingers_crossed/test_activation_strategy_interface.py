from __future__ import annotations

from xtr_logging_contracts import Level

from xtr_logging import ErrorLevelActivationStrategy
from xtr_logging.handler.fingers_crossed.activation_strategy_interface import (
    ActivationStrategyInterface,
)


def test_a_shipped_strategy_satisfies_it() -> None:
    assert isinstance(ErrorLevelActivationStrategy(Level.ERROR), ActivationStrategyInterface)


def test_an_unrelated_object_does_not() -> None:
    assert not isinstance(object(), ActivationStrategyInterface)
