from __future__ import annotations

import pytest

from xtr_http_client_contracts import DecodingError, HttpClientError, JsonError


def test_it_is_a_decoding_error() -> None:
    assert issubclass(JsonError, DecodingError)


def test_it_is_also_a_client_error_and_a_value_error() -> None:
    assert issubclass(JsonError, HttpClientError)
    assert issubclass(JsonError, ValueError)


def test_code_already_catching_a_decoding_error_catches_it() -> None:
    with pytest.raises(DecodingError, match=r"Response body is not an object\."):
        raise JsonError("Response body is not an object.")


def test_it_keeps_the_reason_it_was_given() -> None:
    error = JsonError("Response body is not an object.")

    assert error.reason == "Response body is not an object."
    assert str(error) == "Response body is not an object."
