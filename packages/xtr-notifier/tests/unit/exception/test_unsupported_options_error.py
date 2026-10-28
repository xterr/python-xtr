from __future__ import annotations

from xtr_notifier.exception import LogicError, UnsupportedOptionsError


def test_it_is_a_logic_error() -> None:
    assert issubclass(UnsupportedOptionsError, LogicError)


def test_its_message_names_the_transport_and_both_kinds() -> None:
    error = UnsupportedOptionsError("slack://default", "slack", "telegram")

    assert str(error) == (
        'The "slack://default" transport only supports instances of "slack" '
        'for options (instance of "telegram" given).'
    )
