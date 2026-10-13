from __future__ import annotations

from xtr_http_client_contracts import HttpClientError, TransportError

from xtr_http_client.exception import InvalidArgumentError


def test_it_is_a_transport_error_so_one_except_covers_a_refused_option() -> None:
    error = InvalidArgumentError('Invalid HTTP method "get", only uppercase letters are accepted.')

    assert isinstance(error, TransportError)
    assert isinstance(error, HttpClientError)
    assert isinstance(error, ValueError)


def test_it_carries_the_reason_it_was_built_with() -> None:
    error = InvalidArgumentError("The HTTP method cannot be empty.")

    assert error.reason == "The HTTP method cannot be empty."
    assert str(error) == "The HTTP method cannot be empty."
