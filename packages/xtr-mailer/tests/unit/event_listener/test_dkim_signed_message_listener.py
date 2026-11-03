"""The listener signing every email with DKIM before it is sent."""

from __future__ import annotations

import dkim
from xtr_mime import Address, Email, Message, RawMessage
from xtr_mime.crypto import DkimSigner
from xtr_mime.header import Headers, MailboxListHeader
from xtr_mime.part import TextPart

from tests.support.dkim_keys import SELECTOR, private_key_pem, published_key
from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import DkimSignedMessageListener

_ENVELOPE = Envelope(Address("sender@example.com"), [Address("r1@example.com")])


def _signer() -> DkimSigner:
    return DkimSigner(private_key_pem(), "example.com", SELECTOR)


def test_dkim_message_signing_process() -> None:
    message = Message(
        Headers(MailboxListHeader("From", [Address("sender@example.com")])), TextPart("hello")
    )
    event = MessageEvent(message, _ENVELOPE, "default")

    DkimSignedMessageListener(_signer()).on_message(event)

    signed = event.get_message()
    assert signed is not message
    assert isinstance(signed, Message)
    assert signed.get_headers().has("DKIM-Signature")
    assert not message.get_headers().has("DKIM-Signature")


def test_the_signed_email_verifies_and_keeps_its_bcc() -> None:
    email = (
        Email()
        .from_("sender@example.com")
        .to("r1@example.com")
        .bcc("hidden@example.com")
        .subject("Signed")
        .text("hello")
    )
    event = MessageEvent(email, _ENVELOPE, "default")

    DkimSignedMessageListener(_signer()).on_message(event)

    signed = event.get_message()
    assert isinstance(signed, Message)
    assert signed.get_headers().get_header_body("Bcc") == [Address("hidden@example.com")]
    rendered = b"".join(signed.to_iterable())
    assert b"hidden@example.com" not in rendered
    assert dkim.verify(rendered, dnsfunc=published_key)


def test_raw_bytes_are_sent_unsigned() -> None:
    raw = RawMessage("From: sender@example.com\r\n\r\nhello")
    event = MessageEvent(raw, _ENVELOPE, "default")

    DkimSignedMessageListener(_signer()).on_message(event)

    assert event.get_message() is raw


def test_it_runs_after_the_listeners_changing_the_email_and_before_the_envelope() -> None:
    assert DkimSignedMessageListener.PRIORITY == -228
