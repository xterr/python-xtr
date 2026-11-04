"""An email handed to a provider's API as fields, read from the email rather than its bytes."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_http_client import MockHttpClient, MockResponse
from xtr_mime import (
    Address,
    Email,
    Headers,
    Message,
    MimeRuntimeError,
    MixedPart,
    RawMessage,
    RfcComplianceError,
    TextPart,
)

from xtr_mailer import Envelope, MailerRuntimeError, RemoteTemplateEmail, SentMessage
from xtr_mailer.transport import AbstractApiTransport, RemoteTemplateTransportInterface

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpResponseInterface

pytestmark = pytest.mark.anyio

_NAME = f"{__name__}._ApiTransport"


class _ApiTransport(AbstractApiTransport, RemoteTemplateTransportInterface):
    """Keeps what each call was built from, and answers with the client's response."""

    def __init__(self) -> None:
        super().__init__(MockHttpClient())
        self.calls: list[tuple[SentMessage, Email, Envelope]] = []

    @override
    async def _do_send_api(
        self, sent_message: SentMessage, email: Email, envelope: Envelope
    ) -> HttpResponseInterface:
        self.calls.append((sent_message, email, envelope))
        async with await self._http_client.request(
            "POST", "https://api.example.com/messages"
        ) as response:
            return response

    @override
    def __str__(self) -> str:
        return "api://test"


def _envelope() -> Envelope:
    return Envelope(Address("fabien@example.com"), [Address("helene@example.com")])


def _email() -> Email:
    return Email().from_("fabien@example.com").to("helene@example.com").text("Hello!")


def _message(body: TextPart | MixedPart) -> Message:
    headers = Headers().add_mailbox_list_header("From", ["fabien@example.com"])
    return Message(headers.add_mailbox_list_header("To", ["helene@example.com"]), body)


async def test_send_throws_when_the_original_message_is_not_a_mime_message() -> None:
    transport = _ApiTransport()

    with pytest.raises(MailerRuntimeError) as raised:
        _ = await transport.send(RawMessage("Raw email content"), _envelope())

    assert str(raised.value) == (
        f'Unable to send message with the "{_NAME}" transport: the message must be an instance '
        'of "xtr_mime.Message" (got "xtr_mime.RawMessage"). An API transport builds its payload '
        "from the message fields; use an SMTP transport to send a raw message."
    )
    assert transport.calls == []


async def test_an_email_is_handed_over_as_it_is_with_the_envelope_it_is_sent_with() -> None:
    transport = _ApiTransport()

    sent = await transport.send(_email(), _envelope())

    assert sent is not None
    [(sent_message, email, envelope)] = transport.calls
    assert sent_message is sent
    assert email is sent.get_original_message()
    assert envelope is sent.get_envelope()


async def test_a_message_with_a_simple_body_is_handed_over_as_an_email() -> None:
    transport = _ApiTransport()

    _ = await transport.send(_message(TextPart("Hello!")))

    [(_, email, _)] = transport.calls
    assert email.get_text_body() == "Hello!"
    assert email.get_to() == [Address("helene@example.com")]


async def test_a_message_too_complex_for_an_email_is_refused() -> None:
    transport = _ApiTransport()

    with pytest.raises(MailerRuntimeError) as raised:
        _ = await transport.send(_message(MixedPart()))

    assert str(raised.value) == (
        f'Unable to send message with the "{_NAME}" transport: Unable to create an Email from an '
        'instance of "xtr_mime.Message" as the body is too complex.'
    )
    assert isinstance(raised.value.__cause__, MimeRuntimeError)
    assert transport.calls == []


async def test_the_recipients_are_the_envelope_s_but_the_copies_and_the_hidden_ones() -> None:
    transport = _ApiTransport()
    email = _email().add_to("jane@example.com").cc("cc@example.com").bcc("bcc@example.com")

    _ = await transport.send(email)

    [(_, email, envelope)] = transport.calls
    assert transport._get_recipients(email, envelope) == [
        Address("helene@example.com"),
        Address("jane@example.com"),
    ]


async def test_the_copies_of_a_converted_message_are_left_out_of_the_recipients() -> None:
    transport = _ApiTransport()
    headers = Headers().add_mailbox_list_header("From", ["fabien@example.com"])
    _ = headers.add_mailbox_list_header("To", ["to@example.com"])
    _ = headers.add_mailbox_list_header("Cc", ["cc@example.com"])
    _ = headers.add_mailbox_list_header("Bcc", ["bcc@example.com"])

    _ = await transport.send(Message(headers, TextPart("Hello!")))

    [(_, email, envelope)] = transport.calls
    assert transport._get_recipients(email, envelope) == [Address("to@example.com")]


async def test_the_copies_are_left_out_of_an_envelope_created_from_the_email() -> None:
    transport = _ApiTransport()
    email = _email().cc("cc@example.com").bcc("bcc@example.com")

    _ = await transport.send(email, Envelope.create(email))

    [(_, email, envelope)] = transport.calls
    assert transport._get_recipients(email, envelope) == [Address("helene@example.com")]


async def test_an_envelope_given_keeps_the_recipients_that_are_no_copy_of_the_email() -> None:
    transport = _ApiTransport()
    email = _email().cc("cc@example.com").bcc("bcc@example.com")
    given = Envelope(
        Address("fabien@example.com"),
        [Address("cc@example.com"), Address("extra@example.com"), Address("bcc@example.com")],
    )

    _ = await transport.send(email, given)

    [(_, email, envelope)] = transport.calls
    # A copy reaches its recipient through the provider's own copy field, never twice.
    assert transport._get_recipients(email, envelope) == [Address("extra@example.com")]


async def test_an_email_is_never_rendered_for_the_api() -> None:
    transport = _ApiTransport()

    sent = await transport.send(_email().subject("x" * 1000))

    assert sent is not None
    assert re.fullmatch(r"[0-9a-f]{32}@example\.com", sent.get_message_id())
    with pytest.raises(RfcComplianceError, match="longer than 998 octets"):
        _ = sent.to_string()


async def test_an_email_rendered_from_a_remote_template_is_handed_over() -> None:
    transport = _ApiTransport()
    email = RemoteTemplateEmail().from_("fabien@example.com").to("helene@example.com")

    _ = await transport.send(email.template("welcome", {"name": "Fabien"}))

    [(_, handed, _)] = transport.calls
    assert isinstance(handed, RemoteTemplateEmail)
    assert handed.get_remote_template() is not None


async def test_the_api_exchange_is_logged_on_the_sent_message() -> None:
    transport = _ApiTransport()
    transport._http_client = MockHttpClient(MockResponse(b"{}", {"http_code": 202}))

    sent = await transport.send(_email())

    assert sent is not None
    assert sent.get_debug().startswith("> POST https://api.example.com/messages\n< HTTP/1.1 202")
