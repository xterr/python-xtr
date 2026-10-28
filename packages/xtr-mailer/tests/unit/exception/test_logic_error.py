from __future__ import annotations

from xtr_mailer.exception import LogicError, MailerError


def test_it_is_an_error_of_this_package() -> None:
    assert issubclass(LogicError, MailerError)
    assert issubclass(LogicError, RuntimeError)
