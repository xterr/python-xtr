from __future__ import annotations

from xtr_http_foundation.exception import HttpFoundationError, SessionError


def test_it_derives_from_the_package_base() -> None:
    assert issubclass(SessionError, HttpFoundationError)


def test_it_carries_the_message_it_is_given() -> None:
    assert str(SessionError('The pool could not keep the session "abc".')) == (
        'The pool could not keep the session "abc".'
    )
