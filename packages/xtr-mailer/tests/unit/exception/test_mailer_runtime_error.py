from __future__ import annotations

from xtr_mailer.exception import MailerError, MailerRuntimeError


def test_it_is_a_runtime_error_of_this_package() -> None:
    assert issubclass(MailerRuntimeError, MailerError)
    assert issubclass(MailerRuntimeError, RuntimeError)
