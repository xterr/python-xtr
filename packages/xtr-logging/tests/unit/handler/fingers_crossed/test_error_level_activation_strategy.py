from __future__ import annotations

from tests.support.records import make_record
from xtr_logging import Level
from xtr_logging.handler.fingers_crossed.error_level_activation_strategy import (
    ErrorLevelActivationStrategy,
)


def test_it_activates_on_a_record_at_the_action_level() -> None:
    strategy = ErrorLevelActivationStrategy(Level.WARNING)

    assert strategy.is_handler_activated(make_record(Level.WARNING))


def test_it_activates_on_a_record_above_the_action_level() -> None:
    strategy = ErrorLevelActivationStrategy(Level.WARNING)

    assert strategy.is_handler_activated(make_record(Level.ERROR))


def test_it_does_not_activate_below_the_action_level() -> None:
    strategy = ErrorLevelActivationStrategy(Level.WARNING)

    assert not strategy.is_handler_activated(make_record(Level.INFO))


def test_it_reads_a_level_name() -> None:
    strategy = ErrorLevelActivationStrategy("error")

    assert strategy.is_handler_activated(make_record(Level.ERROR))
    assert not strategy.is_handler_activated(make_record(Level.WARNING))
