from __future__ import annotations

import pytest
from xtr_messenger import InvalidTransportOptionError, UnknownTransportOptionError

from xtr_orm_messenger.transport import ORM_OPTIONS, OrmOptions


def test_the_defaults_are_the_documented_ones() -> None:
    options = OrmOptions.from_settings({})

    assert options == OrmOptions(
        table_name="messenger_messages",
        queue="default",
        redeliver_timeout=3600,
        auto_setup=True,
        poll_interval=1.0,
        transactional=False,
        use_notify=True,
        check_delayed_interval=60_000,
        get_notify_timeout=60_000,
    )


def test_every_setting_is_read_from_the_settings() -> None:
    options = OrmOptions.from_settings(
        {
            "table_name": "jobs",
            "queue": "high",
            "redeliver_timeout": "60",
            "auto_setup": "false",
            "poll_interval": "0.5",
            "transactional": "true",
            "use_notify": "false",
            "check_delayed_interval": "1000",
            "get_notify_timeout": "2000",
        }
    )

    assert options == OrmOptions("jobs", "high", 60, False, 0.5, True, False, 1000, 2000)


def test_a_setting_it_does_not_know_is_refused() -> None:
    with pytest.raises(UnknownTransportOptionError) as refusal:
        _ = OrmOptions.from_settings({"exchange": "x"})

    assert refusal.value.unknown == ("exchange",)
    assert set(refusal.value.known) == set(ORM_OPTIONS)


def test_a_value_its_setting_does_not_take_is_refused() -> None:
    with pytest.raises(InvalidTransportOptionError):
        _ = OrmOptions.from_settings({"redeliver_timeout": "soon"})


@pytest.mark.parametrize("table_name", ["", "messages; drop table x", "1st", "my-table"])
def test_a_table_name_that_is_not_a_plain_identifier_is_refused(table_name: str) -> None:
    with pytest.raises(InvalidTransportOptionError) as refusal:
        _ = OrmOptions(table_name=table_name)

    assert refusal.value.option == "table_name"


@pytest.mark.parametrize("queue", ["", "q" * 191])
def test_a_queue_that_does_not_fit_its_column_is_refused(queue: str) -> None:
    with pytest.raises(InvalidTransportOptionError) as refusal:
        _ = OrmOptions(queue=queue)

    assert refusal.value.option == "queue"


@pytest.mark.parametrize(
    ("option", "settings"),
    [
        ("redeliver_timeout", {"redeliver_timeout": "0"}),
        ("poll_interval", {"poll_interval": "-1"}),
        ("check_delayed_interval", {"check_delayed_interval": "0"}),
        ("get_notify_timeout", {"get_notify_timeout": "-5"}),
    ],
)
def test_a_duration_that_is_not_positive_is_refused(option: str, settings: dict[str, str]) -> None:
    with pytest.raises(InvalidTransportOptionError) as refusal:
        _ = OrmOptions.from_settings(settings)

    assert refusal.value.option == option
