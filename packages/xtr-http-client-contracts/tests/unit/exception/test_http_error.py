from __future__ import annotations

import pytest

from tests.support.fake_response import FakeResponse
from xtr_http_client_contracts import (
    ClientError,
    HttpClientError,
    HttpError,
    RedirectionError,
    ServerError,
)


def test_it_keeps_the_response_it_is_about() -> None:
    response = FakeResponse(status_code=404)

    error = HttpError(response, 'HTTP 404 returned for "https://example.com/".')

    assert error.response is response


def test_the_message_is_composed_from_the_reason_it_was_given() -> None:
    error = HttpError(FakeResponse(), 'HTTP 404 returned for "https://example.com/".')

    assert error.reason == 'HTTP 404 returned for "https://example.com/".'
    assert str(error) == 'HTTP 404 returned for "https://example.com/".'


def test_it_is_a_client_error() -> None:
    assert issubclass(HttpError, HttpClientError)


@pytest.mark.parametrize("error", [ClientError, ServerError, RedirectionError])
def test_the_error_of_every_status_range_keeps_the_response(
    error: type[HttpError],
) -> None:
    response = FakeResponse()

    assert error(response, "reason").response is response


def test_one_catch_handles_every_status_a_server_answered_with() -> None:
    with pytest.raises(HttpError):
        raise ServerError(FakeResponse(status_code=503), "reason")
