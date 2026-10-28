from __future__ import annotations

from xtr_http_client.response.mock_response import MockResponse

from xtr_notifier.exception import NotifierRuntimeError, TransportError


def test_it_is_a_runtime_failure() -> None:
    assert issubclass(TransportError, NotifierRuntimeError)
    assert issubclass(TransportError, RuntimeError)


def test_it_carries_the_response_and_its_debug_trace() -> None:
    response = MockResponse(b"", {"debug": "* Connected"})

    error = TransportError("Unable to post the message.", response)

    assert str(error) == "Unable to post the message."
    assert error.response is response
    assert error.debug == "* Connected"


def test_its_debug_trace_is_empty_when_the_client_kept_none() -> None:
    assert TransportError("failed", MockResponse()).debug == ""


def test_it_carries_no_response_when_the_provider_never_answered() -> None:
    error = TransportError("Could not reach the remote server.")

    assert error.response is None
    assert error.debug == ""
