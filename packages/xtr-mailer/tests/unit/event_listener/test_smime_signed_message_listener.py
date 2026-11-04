"""The listener signing every email with S/MIME before it is sent."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_mime import Address, Email, Message, RawMessage
from xtr_mime.crypto import SMimeSigner
from xtr_mime.header import Headers, MailboxListHeader
from xtr_mime.part import SMimePart, TextPart

from tests.support.smime_checks import verifies
from tests.support.smime_identities import authority, identity
from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import (
    DkimSignedMessageListener,
    SmimeEncryptedMessageListener,
    SmimeSignedMessageListener,
)

if TYPE_CHECKING:
    from pathlib import Path

_ENVELOPE = Envelope(Address("sender@example.com"), [Address("r1@example.com")])


def _signer(directory: Path) -> SMimeSigner:
    certificate, key = identity("sender@example.com").write(directory, "sign")
    return SMimeSigner(certificate, key)


def test_smime_message_signing_process(tmp_path: Path) -> None:
    message = Message(
        Headers(MailboxListHeader("From", [Address("sender@example.com")])), TextPart("hello")
    )
    event = MessageEvent(message, _ENVELOPE, "default")

    SmimeSignedMessageListener(_signer(tmp_path)).on_message(event)

    signed = event.get_message()
    assert signed is not message
    assert isinstance(message.get_body(), TextPart)
    assert isinstance(signed, Message)
    assert isinstance(signed.get_body(), SMimePart)


def test_the_signed_email_verifies_and_keeps_its_bcc(tmp_path: Path) -> None:
    email = (
        Email()
        .from_("sender@example.com")
        .to("r1@example.com")
        .bcc("hidden@example.com")
        .subject("Signed")
        .text("hello")
    )
    event = MessageEvent(email, _ENVELOPE, "default")

    SmimeSignedMessageListener(_signer(tmp_path)).on_message(event)

    signed = event.get_message()
    assert isinstance(signed, Message)
    assert signed.get_headers().get_header_body("Bcc") == [Address("hidden@example.com")]
    rendered = b"".join(signed.to_iterable())
    assert b"hidden@example.com" not in rendered
    assert verifies(rendered, authority().certificate)


def test_raw_bytes_are_sent_unsigned(tmp_path: Path) -> None:
    raw = RawMessage("From: sender@example.com\r\n\r\nhello")
    event = MessageEvent(raw, _ENVELOPE, "default")

    SmimeSignedMessageListener(_signer(tmp_path)).on_message(event)

    assert event.get_message() is raw


def test_it_signs_before_encrypting_and_before_dkim_signs() -> None:
    assert SmimeSignedMessageListener.PRIORITY == -128
    assert SmimeSignedMessageListener.PRIORITY > SmimeEncryptedMessageListener.PRIORITY
    assert SmimeSignedMessageListener.PRIORITY > DkimSignedMessageListener.PRIORITY
