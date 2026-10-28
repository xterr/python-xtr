from __future__ import annotations

from xtr_notifier.exception import LogicError, UnsupportedMessageTypeError


class _Other:
    pass


def test_it_is_a_logic_error() -> None:
    assert issubclass(UnsupportedMessageTypeError, LogicError)


def test_its_message_names_the_transport_and_both_types() -> None:
    error = UnsupportedMessageTypeError("slack://default", "ChatMessage", _Other())

    assert str(error) == (
        'The "slack://default" transport only supports instances of "ChatMessage" '
        '(instance of "_Other" given).'
    )
    assert error.given == "_Other"
