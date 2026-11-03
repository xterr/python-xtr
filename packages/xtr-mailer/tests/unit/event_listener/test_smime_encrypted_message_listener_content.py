"""What the S/MIME encrypting listener encrypts, for whom, and what it refuses to be built with."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_mime import Address, Email, Message, RawMessage
from xtr_mime import InvalidArgumentError as MimeInvalidArgumentError

from tests.support.smime_checks import decrypt
from tests.support.smime_identities import identity
from xtr_mailer import Envelope
from xtr_mailer.event import MessageEvent
from xtr_mailer.event_listener import (
    InMemorySmimeCertificateRepository,
    SmimeEncryptedMessageListener,
)
from xtr_mailer.event_listener import smime_encrypted_message_listener as listener_module
from xtr_mailer.exception import InvalidArgumentError, LogicError

if TYPE_CHECKING:
    from pathlib import Path

_Listener = SmimeEncryptedMessageListener


def _repository(directory: Path, *addresses: str) -> InMemorySmimeCertificateRepository:
    return InMemorySmimeCertificateRepository(
        {address: str(identity(address).write(directory, address)[0]) for address in addresses}
    )


def _email() -> Email:
    email = (
        Email()
        .from_("sender@example.com")
        .to("r1@example.com")
        .cc("r1@example.com")
        .bcc("hidden@example.com")
        .subject("Secret")
        .text("hello")
    )
    _ = email.get_headers().add_text_header("X-SMime-Encrypt", "true")
    return email


def _encrypted(event: MessageEvent) -> bytes:
    message = event.get_message()
    assert isinstance(message, Message)
    return b"".join(message.to_iterable())


def test_every_envelope_recipient_decrypts_the_email_hidden_ones_included(tmp_path: Path) -> None:
    email = _email()
    event = MessageEvent(email, Envelope.create(email), "default")

    _Listener(_repository(tmp_path, "r1@example.com", "hidden@example.com")).on_message(event)

    sent = _encrypted(event)
    for reader in ("r1@example.com", "hidden@example.com"):
        content = decrypt(sent, identity(reader))
        assert b"Subject: Secret\r\n" in content
        assert b"hello" in content
        assert b"X-SMime-Encrypt" not in content
        assert b"hidden@example.com" not in content
    assert b"hidden@example.com" not in sent
    assert b"X-SMime-Encrypt" not in sent


def test_the_encrypted_email_keeps_its_bcc_for_the_envelope(tmp_path: Path) -> None:
    email = _email()
    event = MessageEvent(email, Envelope.create(email), "default")

    _Listener(_repository(tmp_path, "r1@example.com", "hidden@example.com")).on_message(event)

    encrypted = event.get_message()
    assert isinstance(encrypted, Message)
    assert encrypted.get_headers().get_header_body("Bcc") == [Address("hidden@example.com")]


def test_the_email_given_is_left_as_it_was(tmp_path: Path) -> None:
    email = _email()
    event = MessageEvent(email, Envelope.create(email), "default")

    _Listener(_repository(tmp_path, "r1@example.com", "hidden@example.com")).on_message(event)

    assert email.get_headers().has("X-SMime-Encrypt")
    assert email.get_text_body() == "hello"


def test_the_sender_decrypts_what_is_encrypted_for_it_too(tmp_path: Path) -> None:
    repository = _repository(tmp_path, "r1@example.com", "sender@example.com")
    email = _email()
    envelope = Envelope(Address("sender@example.com"), [Address("r1@example.com")])
    event = MessageEvent(email, envelope, "default")

    _Listener(repository, encrypt_for_sender=True).on_message(event)

    assert b"hello" in decrypt(_encrypted(event), identity("sender@example.com"))


def test_a_sender_without_a_certificate_is_not_encrypted_for(tmp_path: Path) -> None:
    email = _email()
    envelope = Envelope(Address("sender@example.com"), [Address("r1@example.com")])
    event = MessageEvent(email, envelope, "default")

    _Listener(_repository(tmp_path, "r1@example.com"), encrypt_for_sender=True).on_message(event)

    assert b"hello" in decrypt(_encrypted(event), identity("r1@example.com"))


def test_raw_bytes_are_sent_unencrypted(tmp_path: Path) -> None:
    raw = RawMessage("From: sender@example.com\r\nX-SMime-Encrypt: true\r\n\r\nhello")
    envelope = Envelope(Address("sender@example.com"), [Address("r1@example.com")])
    event = MessageEvent(raw, envelope, "default")

    _Listener(_repository(tmp_path, "r1@example.com")).on_message(event)

    assert event.get_message() is raw


def test_the_cipher_is_the_one_given(tmp_path: Path) -> None:
    email = _email()
    event = MessageEvent(email, Envelope.create(email), "default")
    repository = _repository(tmp_path, "r1@example.com", "hidden@example.com")

    with pytest.raises(MimeInvalidArgumentError, match=r'^The "des" S/MIME cipher'):
        _Listener(repository, cipher="des").on_message(event)


@pytest.mark.parametrize("mode", ["send_unencrypted", "FAIL", ""])
def test_a_mode_that_is_not_known_is_refused(mode: str) -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = _Listener(InMemorySmimeCertificateRepository(), on_missing_certificate=mode)

    assert str(raised.value) == (
        f'The "on_missing_certificate" option must be "fail", "encrypt" or "skip" (got "{mode}").'
    )


def _absent(name: str) -> None:
    del name


def test_it_is_refused_without_the_smime_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(listener_module, "find_spec", _absent)

    with pytest.raises(LogicError) as raised:
        _ = _Listener(InMemorySmimeCertificateRepository())

    assert str(raised.value) == (
        'The "smime" extra is required to use S/MIME: uv add "xtr-mailer[smime]".'
    )
