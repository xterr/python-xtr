"""An email handed to a provider with one HTTP request, the exchange logged, its errors ours."""

from __future__ import annotations

import pytest
from xtr_http_client import MockHttpClient, MockResponse
from xtr_mime import Email, RfcComplianceError

from tests.support.posting_http_transport import PostingHttpTransport
from tests.support.recorded_events import recording_dispatcher
from xtr_mailer import HttpTransportError, TransportError
from xtr_mailer.event import FailedMessageEvent, MessageEvent
from xtr_mailer.transport import AbstractHttpTransport

pytestmark = pytest.mark.anyio

_OK = b'{"id": "queued-42"}'


def _email() -> Email:
    return Email().from_("fabien@example.com").to("helene@example.com").text("Hello!")


def test_the_http_client_is_required() -> None:
    # Only the three after it have a default: the dispatcher, the logger and the clock.
    assert len(AbstractHttpTransport.__init__.__defaults__ or ()) == 3


async def test_the_provider_is_reached_at_its_own_host_unless_one_is_set() -> None:
    answer = MockResponse(_OK)

    _ = await PostingHttpTransport(MockHttpClient(answer)).send(_email())

    assert answer.get_request_url() == "https://api.example.com/send"


async def test_the_host_and_the_port_can_be_set() -> None:
    answer = MockResponse(_OK)
    transport = PostingHttpTransport(MockHttpClient(answer))

    assert transport.set_host("eu.example.com").set_port(8443) is transport
    _ = await transport.send(_email())

    assert answer.get_request_url() == "https://eu.example.com:8443/send"


async def test_the_message_id_is_the_one_the_provider_answered_with() -> None:
    sent = await PostingHttpTransport(MockHttpClient(MockResponse(_OK))).send(_email())

    assert sent is not None
    assert sent.get_message_id() == "queued-42"


async def test_the_exchange_is_logged_on_the_sent_message() -> None:
    answer = MockResponse(_OK, {"response_headers": ["X-Request-Id: r-7"]})

    sent = await PostingHttpTransport(MockHttpClient(answer)).send(_email())

    assert sent is not None
    debug = sent.get_debug()
    assert debug.startswith("> POST https://api.example.com/send\n< HTTP/1.1 200 OK\n")
    assert "< X-Request-Id: r-7\n" in debug


async def test_the_credential_the_provider_is_called_with_is_never_logged() -> None:
    sent = await PostingHttpTransport(MockHttpClient(MockResponse(_OK))).send(_email())

    assert sent is not None
    assert "secret" not in sent.get_debug()
    assert "Authorization" not in sent.get_debug()


async def test_a_refusal_of_the_transport_gets_the_exchange_logged() -> None:
    transport = PostingHttpTransport(MockHttpClient(MockResponse(b"{}", {"http_code": 400})))
    transport.refuse_itself = True

    with pytest.raises(HttpTransportError) as raised:
        _ = await transport.send(_email())

    assert str(raised.value) == "Refused."
    assert raised.value.debug.startswith("> POST https://api.example.com/send\n< HTTP/1.1 400")


async def test_a_status_the_client_raises_for_is_a_refusal_carrying_the_answer() -> None:
    answer = MockResponse(b'{"message": "down"}', {"http_code": 503})

    with pytest.raises(HttpTransportError) as raised:
        _ = await PostingHttpTransport(MockHttpClient(answer)).send(_email())

    assert str(raised.value) == (
        'Unable to send an email: the provider of the "posting://api.example.com" transport '
        "answered with HTTP 503."
    )
    assert raised.value.code == 503
    assert raised.value.response.get_status_code() == 503
    assert raised.value.debug.startswith("> POST https://api.example.com/send\n< HTTP/1.1 503")


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"not json", id="invalid-json"),
        pytest.param(b"\xff\xfe\x00{", id="not-utf-8"),
        pytest.param(b"[1, 2]", id="not-an-object"),
        pytest.param(b"", id="empty"),
    ],
)
async def test_an_answer_that_cannot_be_read_is_a_transport_error(body: bytes) -> None:
    with pytest.raises(TransportError) as raised:
        _ = await PostingHttpTransport(MockHttpClient(MockResponse(body))).send(_email())

    assert type(raised.value) is TransportError
    assert str(raised.value) == (
        'Unable to send an email: the provider of the "posting://api.example.com" transport '
        "answered with a body that cannot be read."
    )


async def test_a_provider_that_cannot_be_reached_is_a_transport_error() -> None:
    answer = MockResponse(info={"error": "Connection refused for https://api:key-secret@x/"})

    with pytest.raises(TransportError) as raised:
        _ = await PostingHttpTransport(MockHttpClient(answer)).send(_email())

    assert type(raised.value) is TransportError
    assert str(raised.value) == (
        'Could not reach the provider of the "posting://api.example.com" transport '
        "(TransportError)."
    )
    assert raised.value.__suppress_context__


async def test_an_email_the_engine_refuses_is_never_posted() -> None:
    dispatcher, recorded = recording_dispatcher()
    client = MockHttpClient(MockResponse(_OK))

    with pytest.raises(RfcComplianceError):
        _ = await PostingHttpTransport(client, dispatcher).send(_email().subject("x" * 1000))

    assert client.get_requests_count() == 0
    assert [type(event) for event in recorded] == [MessageEvent, FailedMessageEvent]
