from __future__ import annotations

from xtr_notifier.exception import NotifierError


def test_it_is_an_exception_every_error_here_derives_from() -> None:
    assert issubclass(NotifierError, Exception)
