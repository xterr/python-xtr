"""The full set of settings an AMQP transport reads from its configuration."""

from __future__ import annotations

import pytest
from xtr_messenger import InvalidTransportOptionError
from xtr_messenger.bridge.taskiq.taskiq_worker import default_max_async_tasks

from xtr_amqp_messenger.transport.amqp_options import AMQP_OPTIONS, AmqpOptions
from xtr_amqp_messenger.transport.reliability import Reliability


def test_the_defaults() -> None:
    options = AmqpOptions()

    assert options.prefetch_count == 10
    assert options.max_async_tasks == default_max_async_tasks()
    assert options.auto_setup is True
    assert options.delay == "auto"
    assert options.reliability == Reliability()


def test_the_option_list_names_every_group() -> None:
    for setting in (
        "prefetch_count",
        "max_async_tasks",
        "auto_setup",
        "delay",
        "delayed_message_exchange_plugin",
        "max_attempts",
        "exchange",
        "queue",
        "heartbeat",
    ):
        assert setting in AMQP_OPTIONS


def test_from_settings_composes_every_group() -> None:
    options = AmqpOptions.from_settings(
        {
            "prefetch_count": "50",
            "auto_setup": "false",
            "max_attempts": "10",
            "exchange": "jobs.ex",
            "queue_type": "classic",
            "heartbeat": "30",
        },
    )

    assert options.prefetch_count == 50
    assert options.auto_setup is False
    assert options.reliability.max_attempts == 10
    assert options.exchange.name == "jobs.ex"
    assert options.queue.type == "classic"
    assert options.connection.heartbeat == 30.0


def test_options_given_in_code_are_the_defaults_the_settings_override() -> None:
    """A DSN lives in an environment variable; options let code override it,
    while everything the settings do not mention keeps the coded default."""
    built = AmqpOptions.from_settings(
        {"max_attempts": "7"},
        AmqpOptions(reliability=Reliability(base_delay_seconds=9.0), prefetch_count=99),
    )

    assert built.reliability.max_attempts == 7
    assert built.reliability.base_delay_seconds == 9.0
    assert built.prefetch_count == 99


def test_a_non_numeric_prefetch_count_is_refused() -> None:
    with pytest.raises(InvalidTransportOptionError, match="prefetch_count"):
        _ = AmqpOptions.from_settings({"prefetch_count": "many"})


def test_max_async_tasks_is_read_from_the_settings() -> None:
    assert AmqpOptions.from_settings({"max_async_tasks": "7"}).max_async_tasks == 7


def test_max_async_tasks_given_in_code_is_kept_when_the_settings_say_nothing() -> None:
    assert AmqpOptions.from_settings({}, AmqpOptions(max_async_tasks=3)).max_async_tasks == 3


@pytest.mark.parametrize("value", ["0", "-5", "many"])
def test_a_max_async_tasks_that_is_not_a_positive_number_is_refused(value: str) -> None:
    with pytest.raises(InvalidTransportOptionError, match="max_async_tasks"):
        _ = AmqpOptions.from_settings({"max_async_tasks": value})


@pytest.mark.parametrize("value", [0, -5])
def test_a_max_async_tasks_built_in_code_below_one_is_refused(value: int) -> None:
    """Constructed directly, not only through settings: the package error is
    raised rather than a KeyError from a value that never came from settings."""
    with pytest.raises(InvalidTransportOptionError, match="max_async_tasks"):
        _ = AmqpOptions(max_async_tasks=value)


def test_auto_setup_must_be_a_boolean() -> None:
    with pytest.raises(InvalidTransportOptionError, match="auto_setup"):
        _ = AmqpOptions.from_settings({"auto_setup": "yes"})


@pytest.mark.parametrize("delay", ["auto", "native", "plugin", "queue"])
def test_the_delay_is_read_from_the_settings(delay: str) -> None:
    assert AmqpOptions.from_settings({"delay": delay}).delay == delay


@pytest.mark.parametrize(("plugin", "delay"), [("true", "plugin"), ("false", "auto")])
def test_the_plugin_setting_still_chooses_how_to_delay(plugin: str, delay: str) -> None:
    options = AmqpOptions.from_settings({"delayed_message_exchange_plugin": plugin})

    assert options.delay == delay


def test_the_delay_setting_wins_over_the_plugin_setting() -> None:
    options = AmqpOptions.from_settings(
        {"delay": "queue", "delayed_message_exchange_plugin": "true"}
    )

    assert options.delay == "queue"


def test_an_unknown_delay_is_refused() -> None:
    with pytest.raises(InvalidTransportOptionError, match="delay"):
        _ = AmqpOptions.from_settings({"delay": "later"})


def test_a_native_delay_is_refused_for_queues_that_cannot_hold_one() -> None:
    with pytest.raises(InvalidTransportOptionError, match="quorum"):
        _ = AmqpOptions.from_settings({"delay": "native", "queue_type": "classic"})


def test_the_delay_plugin_must_be_a_boolean() -> None:
    with pytest.raises(InvalidTransportOptionError, match="delayed_message_exchange_plugin"):
        _ = AmqpOptions.from_settings({"delayed_message_exchange_plugin": "maybe"})
