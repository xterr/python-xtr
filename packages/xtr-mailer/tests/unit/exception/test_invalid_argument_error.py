from __future__ import annotations

from xtr_mailer.exception import InvalidArgumentError, MailerError


def test_it_is_an_error_of_this_package_and_a_value_error() -> None:
    assert issubclass(InvalidArgumentError, MailerError)
    assert issubclass(InvalidArgumentError, ValueError)
