from __future__ import annotations

from xtr_logging_contracts import Level

from tests.support.records import make_record
from xtr_logging.handler.fingers_crossed.channel_level_activation_strategy import (
    ChannelLevelActivationStrategy,
)


def test_it_uses_the_default_level_for_an_unlisted_channel() -> None:
    strategy = ChannelLevelActivationStrategy(Level.ERROR, {"sql": Level.WARNING})

    assert strategy.is_handler_activated(make_record(Level.ERROR, channel="app"))
    assert not strategy.is_handler_activated(make_record(Level.WARNING, channel="app"))


def test_it_uses_a_channels_own_level_when_listed() -> None:
    strategy = ChannelLevelActivationStrategy(Level.ERROR, {"sql": Level.WARNING})

    assert strategy.is_handler_activated(make_record(Level.WARNING, channel="sql"))


def test_a_listed_channel_below_its_level_does_not_activate() -> None:
    strategy = ChannelLevelActivationStrategy(Level.ERROR, {"sql": Level.WARNING})

    assert not strategy.is_handler_activated(make_record(Level.INFO, channel="sql"))


def test_the_channel_map_is_optional() -> None:
    strategy = ChannelLevelActivationStrategy(Level.ERROR)

    assert strategy.is_handler_activated(make_record(Level.ERROR, channel="anything"))
    assert not strategy.is_handler_activated(make_record(Level.WARNING, channel="anything"))


def test_it_reads_level_names() -> None:
    strategy = ChannelLevelActivationStrategy("error", {"sql": "warning"})

    assert strategy.is_handler_activated(make_record(Level.WARNING, channel="sql"))
    assert not strategy.is_handler_activated(make_record(Level.WARNING, channel="app"))
