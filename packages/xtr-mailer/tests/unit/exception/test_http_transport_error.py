from __future__ import annotations

from xtr_http_client.response.mock_response import MockResponse

from xtr_mailer.exception import HttpTransportError, TransportError


def test_it_is_a_transport_error() -> None:
    assert issubclass(HttpTransportError, TransportError)


def test_it_carries_the_response() -> None:
    response = MockResponse(b'{"message": "Forbidden"}', {"http_code": 401})

    error = HttpTransportError("Unable to send an email: Forbidden (code 401).", response, 401)

    assert str(error) == "Unable to send an email: Forbidden (code 401)."
    assert error.response is response
    assert error.code == 401
    assert error.debug == ""
