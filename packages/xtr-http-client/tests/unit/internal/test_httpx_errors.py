from __future__ import annotations

import httpx
import pytest

from xtr_http_client.exception import (
    InvalidArgumentError,
    TransportError,
    TransportTimeoutError,
)
from xtr_http_client.internal.httpx_errors import timed_out, transport_error

_URL = "http://example.com/orders"


def test_a_timeout_from_the_backend_is_a_transport_timeout() -> None:
    error = transport_error(httpx.ReadTimeout("too slow"), _URL)

    assert isinstance(error, TransportTimeoutError)
    assert error.reason == 'too slow for "http://example.com/orders".'


@pytest.mark.parametrize(
    "failure",
    [httpx.UnsupportedProtocol("no such scheme"), httpx.InvalidURL("not a URL")],
)
def test_a_url_the_backend_cannot_use_is_an_invalid_argument(failure: Exception) -> None:
    assert isinstance(transport_error(failure, _URL), InvalidArgumentError)


def test_anything_else_from_the_backend_is_a_transport_error() -> None:
    error = transport_error(httpx.ConnectError("refused"), _URL)

    assert type(error) is TransportError


def test_a_failure_with_no_message_is_named_by_its_class() -> None:
    error = transport_error(httpx.ConnectError(""), _URL)

    assert error.reason == 'ConnectError for "http://example.com/orders".'


def test_running_out_of_the_whole_duration_is_a_timeout_naming_the_url() -> None:
    error = timed_out(_URL)

    assert isinstance(error, TransportTimeoutError)
    assert error.reason == 'Maximum duration reached for "http://example.com/orders".'
