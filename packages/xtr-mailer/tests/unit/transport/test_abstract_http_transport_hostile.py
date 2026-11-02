"""An HTTP send cut short, run alongside another, or answered with what it does not expect."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import pytest
from xtr_http_client import MockHttpClient, MockResponse
from xtr_http_client_contracts.exception import TransportTimeoutError
from xtr_mime import Email

from tests.support.posting_http_transport import PostingHttpTransport
from tests.support.recorded_events import recording_dispatcher
from xtr_mailer import HttpTransportError, SentMessage, TransportError
from xtr_mailer.event import MessageEvent

if TYPE_CHECKING:
    from xtr_http_client_contracts import RequestOptions

pytestmark = pytest.mark.anyio


def _email() -> Email:
    return Email().from_("fabien@example.com").to("helene@example.com").text("Hello!")


async def _stall(method: str, url: str, options: RequestOptions) -> MockResponse:
    del method, url, options
    await anyio.sleep_forever()
    raise AssertionError  # pragma: no cover -- never woken.


async def _time_out(method: str, url: str, options: RequestOptions) -> MockResponse:
    del method, options
    raise TransportTimeoutError(f"Idle timeout reached for {url}.")


async def test_a_cancelled_send_is_neither_sent_nor_failed() -> None:
    dispatcher, recorded = recording_dispatcher()
    transport = PostingHttpTransport(MockHttpClient(_stall), dispatcher)

    with anyio.move_on_after(0.01) as scope:
        _ = await transport.send(_email())

    assert scope.cancelled_caught
    assert [type(event) for event in recorded] == [MessageEvent]


async def test_a_timeout_is_a_transport_error() -> None:
    with pytest.raises(TransportError) as raised:
        _ = await PostingHttpTransport(MockHttpClient(_time_out)).send(_email())

    assert str(raised.value) == (
        'Could not reach the provider of the "posting://api.example.com" transport '
        "(TransportTimeoutError)."
    )
    assert "example.com/send" not in str(raised.value)


async def test_sends_running_at_once_each_log_their_own_exchange() -> None:
    answers = [
        MockResponse(b'{"id": "first"}', {"response_headers": ["X-Answer: first"]}),
        MockResponse(b'{"id": "second"}', {"response_headers": ["X-Answer: second"]}),
    ]
    transport = PostingHttpTransport(MockHttpClient(answers))
    sent: list[SentMessage | None] = []

    async def send() -> None:
        sent.append(await transport.send(_email()))

    async with anyio.create_task_group() as group:
        _ = group.start_soon(send)
        _ = group.start_soon(send)

    for each in sent:
        assert each is not None
        assert each.get_debug().count("> POST") == 1
        assert f"< X-Answer: {each.get_message_id()}\n" in each.get_debug()


async def test_a_huge_refusal_is_carried_without_its_body_in_the_error() -> None:
    body = b"x" * (3 * 1024 * 1024)
    answer = MockResponse(body, {"http_code": 500})

    with pytest.raises(HttpTransportError) as raised:
        _ = await PostingHttpTransport(MockHttpClient(answer)).send(_email())

    assert len(str(raised.value)) < 200
    assert "xxxx" not in raised.value.debug


async def test_a_cookie_the_provider_sets_is_never_logged() -> None:
    answer = MockResponse(b'{"id": "1"}', {"response_headers": ["Set-Cookie: session=secret"]})

    sent = await PostingHttpTransport(MockHttpClient(answer)).send(_email())

    assert sent is not None
    assert "< Set-Cookie: [redacted]\n" in sent.get_debug()
    assert "secret" not in sent.get_debug()
