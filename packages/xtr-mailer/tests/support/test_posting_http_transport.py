from __future__ import annotations

import pytest
from xtr_http_client import MockHttpClient, MockResponse
from xtr_mime import Email

from tests.support.posting_http_transport import PostingHttpTransport
from xtr_mailer import HttpTransportError

pytestmark = pytest.mark.anyio


def _email() -> Email:
    return Email().from_("fabien@example.com").to("helene@example.com").text("Hello!")


async def test_it_posts_the_rendered_email_and_keeps_the_id_answered() -> None:
    answer = MockResponse(b'{"id": "42"}')

    sent = await PostingHttpTransport(MockHttpClient(answer)).send(_email())

    assert sent is not None
    assert sent.get_message_id() == "42"
    assert answer.get_request_url() == "https://api.example.com/send"
    body = answer.get_request_options()["body"]
    assert isinstance(body, bytes)
    assert b"Hello!" in body


async def test_it_refuses_itself_when_told_to() -> None:
    transport = PostingHttpTransport(MockHttpClient(MockResponse(b"{}", {"http_code": 400})))
    transport.refuse_itself = True

    with pytest.raises(HttpTransportError, match=r"^Refused\.$"):
        _ = await transport.send(_email())


def test_it_is_named_after_its_provider() -> None:
    assert str(PostingHttpTransport(MockHttpClient())) == "posting://api.example.com"
