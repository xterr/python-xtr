"""A signed email handed to a transport: DKIM keeps its fields and Bcc, an API refuses S/MIME."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from typing_extensions import override
from xtr_event_dispatcher import EventDispatcher
from xtr_http_client import MockHttpClient
from xtr_mime import Email, MimeRuntimeError
from xtr_mime.crypto import DkimSigner, SMimeSigner

from tests.support.certificates import make_certificate
from tests.support.fake_transport import FakeTransport
from xtr_mailer import Envelope, MailerRuntimeError
from xtr_mailer.event import MessageEvent
from xtr_mailer.transport import AbstractApiTransport

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_event_dispatcher_contracts import EventDispatcherInterface
    from xtr_http_client_contracts import HttpResponseInterface
    from xtr_mime import Address

    from xtr_mailer import SentMessage

pytestmark = pytest.mark.anyio


class _ApiTransport(AbstractApiTransport):
    """Keeps the email each call was built from, and who it went ``to``."""

    def __init__(self, event_dispatcher: EventDispatcherInterface | None = None) -> None:
        super().__init__(MockHttpClient(), event_dispatcher)
        self.emails: list[Email] = []
        self.recipients: list[list[str]] = []

    @override
    async def _do_send_api(
        self, sent_message: SentMessage, email: Email, envelope: Envelope
    ) -> HttpResponseInterface:
        self.emails.append(email)
        self.recipients.append(_addresses(self._get_recipients(email, envelope)))
        async with await self._http_client.request("POST", "https://api.example.com/") as answer:
            return answer

    @override
    def __str__(self) -> str:
        return "api://test"


@cache
def _dkim_key() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode("ascii")


def _email() -> Email:
    return (
        Email()
        .from_("fabien@example.com")
        .to("helene@example.com")
        .text("Hello!")
        .html('<p>Hello! <img src="cid:logo.gif"></p>')
        .embed(b"GIF89a", "logo.gif", "image/gif")
        .attach(b"total: 42", "invoice.txt", "text/plain")
    )


def _attachments(email: Email) -> list[tuple[str | None, str, str | bytes, bool]]:
    return [
        (part.get_filename(), part.get_content_type(), part.get_body(), part.has_content_id())
        for part in email.get_attachments()
    ]


def _addresses(addresses: list[Address]) -> list[str]:
    return [address.get_address() for address in addresses]


def _copied_email() -> Email:
    return (
        Email()
        .from_("fabien@example.com")
        .to("to@example.com")
        .cc("cc@example.com")
        .bcc("hidden@example.com")
        .text("Hello!")
    )


def _signer() -> DkimSigner:
    return DkimSigner(_dkim_key(), "example.com", "default")


async def test_a_dkim_signed_email_is_handed_over_with_the_parts_it_was_signed_with() -> None:
    transport = _ApiTransport()
    email = _email()
    signed = DkimSigner(_dkim_key(), "example.com", "default").sign(email)

    _ = await transport.send(signed)

    [handed] = transport.emails
    assert handed.get_headers().has("DKIM-Signature")
    assert handed.get_text_body() == "Hello!"
    assert str(handed.get_html_body()).startswith("<p>Hello! <img src=")
    assert _attachments(handed) == [
        ("logo.gif", "image/gif", b"GIF89a", True),
        ("invoice.txt", "text/plain", b"total: 42", False),
    ]


async def test_an_email_signed_by_a_listener_keeps_its_bcc_out_of_the_api_s_to() -> None:
    dispatcher = EventDispatcher()

    def sign(event: MessageEvent) -> None:
        message = event.get_message()
        assert isinstance(message, Email)
        event.set_message(_signer().sign(message))

    dispatcher.add_listener(MessageEvent, sign, -228)
    transport = _ApiTransport(dispatcher)

    _ = await transport.send(_copied_email())

    [handed] = transport.emails
    assert transport.recipients == [["to@example.com"]]
    assert _addresses(handed.get_bcc()) == ["hidden@example.com"]


async def test_an_email_signed_before_its_envelope_was_read_keeps_its_bcc_out_of_the_to() -> None:
    email = _copied_email()
    transport = _ApiTransport()

    _ = await transport.send(_signer().sign(email), Envelope.create(email))

    [handed] = transport.emails
    assert transport.recipients == [["to@example.com"]]
    assert _addresses(handed.get_bcc()) == ["hidden@example.com"]


async def test_an_email_signed_then_sent_through_an_api_is_sent_to_its_bcc() -> None:
    sent = await _ApiTransport().send(_signer().sign(_copied_email()))

    assert sent is not None
    assert _addresses(sent.get_envelope().get_recipients()) == [
        "to@example.com",
        "cc@example.com",
        "hidden@example.com",
    ]


async def test_an_email_signed_then_sent_as_bytes_is_sent_to_its_bcc_never_named() -> None:
    sent = await FakeTransport().send(_signer().sign(_copied_email()))

    assert sent is not None
    assert _addresses(sent.get_envelope().get_recipients()) == [
        "to@example.com",
        "cc@example.com",
        "hidden@example.com",
    ]
    rendered = b"".join(sent.to_iterable())
    assert b"hidden@example.com" not in rendered
    assert b"\r\nbcc:" not in rendered.lower()


async def test_an_s_mime_signed_email_is_refused(tmp_path: Path) -> None:
    certificate = make_certificate(tmp_path)
    signed = SMimeSigner(certificate.cert_path, certificate.key_path).sign(_email())
    transport = _ApiTransport()

    with pytest.raises(MailerRuntimeError) as raised:
        _ = await transport.send(signed)

    assert str(raised.value) == (
        'Unable to send message with the "tests.unit.transport.test_abstract_api_transport_signed.'
        '_ApiTransport" transport: Unable to create an Email from an instance of '
        '"xtr_mime.Message" as the body is signed or encrypted with S/MIME: only the whole '
        "message can be sent."
    )
    assert isinstance(raised.value.__cause__, MimeRuntimeError)
    assert transport.emails == []
