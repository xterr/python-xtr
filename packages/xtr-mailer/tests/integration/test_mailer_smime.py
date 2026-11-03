"""Emails signed and encrypted with S/MIME by the listeners, sent through the mailer over SMTP."""

from __future__ import annotations

from typing import TYPE_CHECKING

import dkim
import pytest
from xtr_event_dispatcher import EventDispatcher
from xtr_mime import Email
from xtr_mime.crypto import DkimSigner, SMimeSigner

from tests.support.dkim_keys import SELECTOR, private_key_pem, published_key
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smime_checks import decrypt, openssl_verifies, verifies
from tests.support.smime_identities import authority, identity
from xtr_mailer import Mailer
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import (
    DkimSignedMessageListener,
    InMemorySmimeCertificateRepository,
    SmimeEncryptedMessageListener,
    SmimeSignedMessageListener,
)
from xtr_mailer.exception import MailerRuntimeError
from xtr_mailer.transport.smtp import EsmtpTransport

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_Listener = DkimSignedMessageListener | SmimeEncryptedMessageListener | SmimeSignedMessageListener


def _email(*, encrypt: bool = False) -> Email:
    email = (
        Email()
        .from_("sender@example.com")
        .to("r1@example.com")
        .cc("r2@example.com")
        .bcc("hidden@example.com")
        .subject("Über alles")
        .text("Line one\n.Line starting with a period\nLine three")
        .html("<p>Hello</p>")
    )
    if encrypt:
        _ = email.get_headers().add_text_header("X-SMime-Encrypt", "true")
    return email


def _signed_by(directory: Path) -> SmimeSignedMessageListener:
    certificate, key = identity("sender@example.com").write(directory, "sign", "secret")
    return SmimeSignedMessageListener(SMimeSigner(certificate, key, passphrase="secret"))


def _encrypted_for(directory: Path, *addresses: str) -> SmimeEncryptedMessageListener:
    certificates = {
        address: str(identity(address).write(directory, address)[0]) for address in addresses
    }
    return SmimeEncryptedMessageListener(InMemorySmimeCertificateRepository(certificates))


def _dkim_signed() -> DkimSignedMessageListener:
    return DkimSignedMessageListener(DkimSigner(private_key_pem(), "example.com", SELECTOR))


async def _send(email: Email, *listeners: _Listener) -> ScriptedSmtpServer:
    dispatcher = EventDispatcher()
    for listener in listeners:
        dispatcher.add_listener(MessageEvent, listener.on_message, priority=listener.PRIORITY)
    async with ScriptedSmtpServer() as server:
        transport = EsmtpTransport("localhost", server.port, event_dispatcher=dispatcher)
        try:
            await Mailer(transport, None, dispatcher).send(email)
        finally:
            await transport.stop()
    return server


def _recipients(server: ScriptedSmtpServer) -> list[str]:
    return [command for command in server.commands if command.startswith(("MAIL", "RCPT"))]


_EVERY_RECIPIENT = [
    "MAIL FROM:<sender@example.com>",
    "RCPT TO:<r1@example.com>",
    "RCPT TO:<r2@example.com>",
    "RCPT TO:<hidden@example.com>",
]


async def test_a_signed_email_verifies_and_reaches_its_hidden_recipient(tmp_path: Path) -> None:
    server = await _send(_email(), _signed_by(tmp_path))

    [received] = server.messages
    assert _recipients(server) == _EVERY_RECIPIENT
    assert b"hidden@example.com" not in received
    assert verifies(received, authority().certificate)
    if (verified := openssl_verifies(received, authority().certificate, tmp_path)) is not None:
        assert verified


async def test_an_encrypted_email_is_decrypted_by_each_recipient(tmp_path: Path) -> None:
    listener = _encrypted_for(tmp_path, "r1@example.com", "r2@example.com", "hidden@example.com")

    server = await _send(_email(encrypt=True), listener)

    [received] = server.messages
    assert _recipients(server) == _EVERY_RECIPIENT
    assert b"hidden@example.com" not in received
    assert b"X-SMime-Encrypt" not in received
    for reader in ("r1@example.com", "r2@example.com", "hidden@example.com"):
        content = decrypt(received, identity(reader))
        assert b"Line three" in content.replace(b"=\r\n", b"")
        assert b"hidden@example.com" not in content


async def test_a_signed_then_encrypted_email_decrypts_to_a_signature_that_verifies(
    tmp_path: Path,
) -> None:
    encrypted = _encrypted_for(tmp_path, "r1@example.com", "r2@example.com", "hidden@example.com")

    server = await _send(_email(encrypt=True), encrypted, _signed_by(tmp_path))

    [received] = server.messages
    content = decrypt(received, identity("r2@example.com"))
    assert verifies(content, authority().certificate)
    if (verified := openssl_verifies(content, authority().certificate, tmp_path)) is not None:
        assert verified


async def test_an_email_signed_with_s_mime_then_dkim_verifies_both_ways(tmp_path: Path) -> None:
    server = await _send(_email(), _dkim_signed(), _signed_by(tmp_path))

    [received] = server.messages
    assert _recipients(server) == _EVERY_RECIPIENT
    assert b"hidden@example.com" not in received
    assert verifies(received, authority().certificate)
    assert dkim.verify(received, dnsfunc=published_key)


async def test_an_encrypted_email_signed_with_dkim_verifies_and_decrypts(tmp_path: Path) -> None:
    encrypted = _encrypted_for(tmp_path, "r1@example.com", "r2@example.com", "hidden@example.com")

    server = await _send(_email(encrypt=True), _dkim_signed(), encrypted)

    [received] = server.messages
    assert dkim.verify(received, dnsfunc=published_key)
    assert b"Line three" in decrypt(received, identity("r1@example.com")).replace(b"=\r\n", b"")


async def test_a_recipient_without_a_certificate_stops_the_email(tmp_path: Path) -> None:
    listener = _encrypted_for(tmp_path, "r1@example.com", "r2@example.com")

    with pytest.raises(MailerRuntimeError) as raised:
        _ = await _send(_email(encrypt=True), listener)

    assert str(raised.value) == (
        'No S/MIME certificate found for recipient(s) "hidden@example.com".'
    )


async def test_a_recipient_without_a_certificate_is_skipped_when_asked(tmp_path: Path) -> None:
    email = _email(encrypt=False)
    _ = email.get_headers().add_text_header("X-SMime-Encrypt", "skip")

    server = await _send(email, _encrypted_for(tmp_path, "r1@example.com", "r2@example.com"))

    [received] = server.messages
    assert _recipients(server) == _EVERY_RECIPIENT[:3]
    assert b"Line three" in decrypt(received, identity("r2@example.com")).replace(b"=\r\n", b"")
