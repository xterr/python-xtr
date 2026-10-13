from __future__ import annotations

import pytest

from xtr_http_client_contracts import (
    ClientError,
    DecodingError,
    HttpClientError,
    HttpError,
    RedirectionError,
    ServerError,
    TransportError,
    TransportTimeoutError,
)


@pytest.mark.parametrize(
    "error",
    [
        TransportError,
        TransportTimeoutError,
        DecodingError,
        HttpError,
        ClientError,
        ServerError,
        RedirectionError,
    ],
)
def test_every_contract_error_derives_from_it(error: type[Exception]) -> None:
    assert issubclass(error, HttpClientError)


def test_it_is_an_exception_like_any_other() -> None:
    assert issubclass(HttpClientError, Exception)
