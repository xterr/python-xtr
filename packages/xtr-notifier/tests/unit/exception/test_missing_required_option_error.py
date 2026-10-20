from __future__ import annotations

from xtr_notifier.exception import IncompleteDsnError, MissingRequiredOptionError


def test_it_is_an_incomplete_dsn() -> None:
    assert issubclass(MissingRequiredOptionError, IncompleteDsnError)


def test_its_message_names_the_option() -> None:
    error = MissingRequiredOptionError("channel")

    assert str(error) == 'The option "channel" is required but missing.'
    assert error.option == "channel"


def test_its_message_names_the_dsn_when_given() -> None:
    error = MissingRequiredOptionError("channel", "slack://default")

    assert str(error) == (
        'Invalid "slack://default" notifier DSN: The option "channel" is required but missing.'
    )
