from __future__ import annotations

from xtr_http_client_contracts import DecodingError, HttpClientError

from xtr_http_client.exception import JsonError


def test_it_is_a_decoding_error_so_one_except_covers_any_unreadable_body() -> None:
    error = JsonError('JSON content was expected to decode to an object, "list" returned.')

    assert isinstance(error, DecodingError)
    assert isinstance(error, HttpClientError)
    assert isinstance(error, ValueError)


def test_it_carries_the_reason_it_was_built_with() -> None:
    error = JsonError("Response body is empty.")

    assert error.reason == "Response body is empty."
    assert str(error) == "Response body is empty."
