"""Signed and encrypted emails come off a serializing bus byte for byte, and still verify.

An email signed before it is queued must reach the server as the bytes signed — with ``simple``
canonicalization, every signed header too. An email queued unsigned is signed by the listeners
of the worker, as upstream's are.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import dkim
import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_mime import Email
from xtr_mime.crypto import DkimOptions, DkimSigner, SMimeEncrypter, SMimeSigner

from tests.support.dkim_keys import SELECTOR, private_key_pem, published_key
from tests.support.queue import through_the_queue
from tests.support.smime_checks import decrypt, verifies
from tests.support.smime_identities import authority, identity
from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import DkimSignedMessageListener
from xtr_mailer.messenger import MessageHandler
from xtr_mailer.transport import NullTransport

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_mime import RawMessage

pytestmark = pytest.mark.anyio


def _email() -> Email:
    return (
        Email()
        .from_("sender@example.com")
        .to("r1@example.com")
        .bcc("hidden@example.com")
        .subject("Über alles — a subject long enough to be folded by the engine, twice over")
        .text("Line one\n.Line starting with a period\nLine three")
        .html("<p>Hello</p>")
        .attach(b"\x00\x01", "data.bin")
    )


def _rendered(message: RawMessage) -> bytes:
    return b"".join(message.to_iterable())


def _dkim(canonicalization: str) -> DkimSigner:
    options = DkimOptions().header_canon(canonicalization).body_canon(canonicalization)
    return DkimSigner(private_key_pem(), "example.com", SELECTOR, default_options=options)


@pytest.mark.parametrize("canonicalization", ["simple", "relaxed"])
async def test_an_email_signed_with_dkim_comes_off_the_queue_byte_for_byte(
    canonicalization: str,
) -> None:
    signed = _dkim(canonicalization).sign(_email())

    queued = await through_the_queue(signed)

    sent = _rendered(queued.message)
    assert sent == _rendered(signed)
    assert dkim.verify(sent, dnsfunc=published_key)
    assert b"hidden@example.com" not in sent
    recipients = Envelope.create(queued.message).get_recipients()
    assert [a.get_address() for a in recipients] == ["r1@example.com", "hidden@example.com"]


async def test_an_email_signed_with_s_mime_comes_off_the_queue_and_verifies(
    tmp_path: Path,
) -> None:
    certificate, key = identity("sender@example.com").write(tmp_path, "sign")
    signed = SMimeSigner(certificate, key).sign(_email())

    queued = await through_the_queue(signed)

    sent = _rendered(queued.message)
    assert sent == _rendered(signed)
    assert verifies(sent, authority().certificate)


async def test_an_email_encrypted_with_s_mime_comes_off_the_queue_and_decrypts(
    tmp_path: Path,
) -> None:
    certificate, _ = identity("r1@example.com").write(tmp_path, "r1")
    encrypted = SMimeEncrypter(str(certificate)).encrypt(_email())

    queued = await through_the_queue(encrypted)

    sent = _rendered(queued.message)
    assert sent == _rendered(encrypted)
    assert b"Line three" in decrypt(sent, identity("r1@example.com")).replace(b"=\r\n", b"")


async def test_an_email_signed_with_s_mime_then_dkim_comes_off_the_queue_verifying_both(
    tmp_path: Path,
) -> None:
    certificate, key = identity("sender@example.com").write(tmp_path, "sign")
    signed = _dkim("simple").sign(SMimeSigner(certificate, key).sign(_email()))

    sent = _rendered((await through_the_queue(signed)).message)

    assert dkim.verify(sent, dnsfunc=published_key)
    assert verifies(sent, authority().certificate)


async def test_an_email_queued_unsigned_is_signed_by_the_listeners_of_the_worker() -> None:
    worker = EventDispatcher()
    listener = DkimSignedMessageListener(_dkim("simple"))
    worker.add_listener(MessageEvent, listener.on_message, priority=listener.PRIORITY)
    queued = await through_the_queue(_email(), None, EventDispatcher())

    sent = await MessageHandler(NullTransport(worker))(queued)

    assert sent is not None
    assert b"DKIM-Signature" not in _rendered(queued.message)
    assert dkim.verify(sent.to_string().encode("utf-8", "surrogateescape"), dnsfunc=published_key)
