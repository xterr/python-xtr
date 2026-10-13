from __future__ import annotations

from xtr_http_client_contracts import HttpClientError, HttpError, TransportError


def test_it_keeps_the_reason_it_was_given_and_says_it() -> None:
    error = TransportError('Could not resolve host "example.invalid".')

    assert error.reason == 'Could not resolve host "example.invalid".'
    assert str(error) == 'Could not resolve host "example.invalid".'


def test_it_is_a_client_error_but_never_an_http_error() -> None:
    assert issubclass(TransportError, HttpClientError)
    assert not issubclass(TransportError, HttpError)
