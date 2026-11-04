from __future__ import annotations

from xtr_mailer.exception import TransportError, UnexpectedResponseError


def test_it_is_a_transport_error() -> None:
    assert issubclass(UnexpectedResponseError, TransportError)


def test_it_carries_the_reply_code() -> None:
    error = UnexpectedResponseError('Expected response code "250" but got code "421".', 421)

    assert error.code == 421
    assert str(error) == 'Expected response code "250" but got code "421".'
