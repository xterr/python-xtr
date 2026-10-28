from __future__ import annotations

from xtr_notifier.exception import IncompleteDsnError, InvalidArgumentError


def test_it_is_an_invalid_argument_and_a_value_error() -> None:
    assert issubclass(IncompleteDsnError, InvalidArgumentError)
    assert issubclass(IncompleteDsnError, ValueError)


def test_its_message_names_the_dsn_when_given() -> None:
    error = IncompleteDsnError("User is not set.", "scheme://default")

    assert str(error) == 'Invalid "scheme://default" notifier DSN: User is not set.'
    assert error.original_dsn == "scheme://default"


def test_its_message_is_the_reason_alone_without_a_dsn() -> None:
    error = IncompleteDsnError("Missing token.")

    assert str(error) == "Missing token."
    assert error.original_dsn is None
