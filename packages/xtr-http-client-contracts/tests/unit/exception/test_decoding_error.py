from __future__ import annotations

import pytest

from xtr_http_client_contracts import DecodingError, HttpClientError


def test_it_is_a_client_error() -> None:
    assert issubclass(DecodingError, HttpClientError)


def test_it_is_also_a_value_error() -> None:
    assert issubclass(DecodingError, ValueError)


def test_code_already_guarding_its_input_catches_it() -> None:
    with pytest.raises(ValueError, match=r"Response body is empty\."):
        raise DecodingError("Response body is empty.")


def test_it_keeps_the_reason_it_was_given() -> None:
    error = DecodingError("Response body is empty.")

    assert error.reason == "Response body is empty."
    assert str(error) == "Response body is empty."
