"""Build signers and encrypters over the run's certificates, and the messages upstream signs."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from tests.support.smime_certificates import authority, recipient, signer_identity
from tests.support.smime_checks import verifies, wire
from xtr_mime import Email, Headers, Message, TextPart
from xtr_mime.crypto import SMimeEncrypter, SMimeSigner

if TYPE_CHECKING:
    from pathlib import Path

    from tests.support.smime_certificates import Identity

__all__ = [
    "assert_headers_kept",
    "assert_signature_holds",
    "email",
    "encrypter",
    "message",
    "signer",
]

_DATE = datetime(2019, 4, 7, 10, 36, 30, tzinfo=ZoneInfo("Europe/Paris"))


def signer(directory: Path, identity: Identity | None = None, passphrase: str = "") -> SMimeSigner:
    """Return a signer reading the certificate and key of ``identity`` from ``directory``."""
    certificate, key = (identity or signer_identity()).write(directory, "sign", passphrase)
    return SMimeSigner(certificate, key, passphrase=passphrase)


def encrypter(directory: Path, *identities: Identity) -> SMimeEncrypter:
    """Return an encrypter for ``identities``, the run's first recipient when none is given."""
    paths = [
        identity.write(directory, f"encrypt{index}")[0]
        for index, identity in enumerate(identities or (recipient(),))
    ]
    return SMimeEncrypter(paths)


def message(text: str = "content") -> Message:
    """Return upstream's plain message: a Date, a From and a text body."""
    headers = Headers().add_date_header("Date", _DATE)
    return Message(headers.add_mailbox_list_header("From", ["fabien@example.com"]), TextPart(text))


def email(to: str = "fabien@example.com", message_id: str = "some@id") -> Email:
    """Return upstream's email, with a Message-ID so that it renders the same every time."""
    built = (
        Email()
        .date(_DATE)
        .to(to)
        .subject("Testing")
        .from_("noreply@example.com")
        .text("El Barto was not here")
    )
    _ = built.get_headers().add_id_header("Message-ID", message_id)
    return built


def assert_headers_kept(result: Message, original: Message) -> None:
    """Check what upstream checks of the headers: Bcc kept but not written, Subject kept."""
    sent = wire(result).lower()
    assert not sent.startswith(b"bcc:")
    assert b"\r\nbcc:" not in sent
    original_bcc = original.get_headers().get("Bcc")
    if original_bcc is not None:
        result_bcc = result.get_headers().get("Bcc")
        assert result_bcc is not None
        assert result_bcc.get_body_as_string() == original_bcc.get_body_as_string()
    original_subject = original.get_headers().get("Subject")
    if original_subject is not None:
        subject = result.get_prepared_headers().get("Subject")
        assert subject is not None
        assert subject.get_body_as_string() == original_subject.get_body_as_string()
        assert b"\r\nsubject:" in sent


def assert_signature_holds(signed: Message, original: Message) -> None:
    """Check the signature verifies, and no longer does once a byte of the signed part changes."""
    sent = wire(signed)
    assert_headers_kept(signed, original)
    assert verifies(sent, authority().certificate)
    tampered = sent.replace(b"Content-Transfer-Encoding: ", b"Content-Transfer-Encoding:  ", 1)
    assert tampered != sent
    assert not verifies(tampered, authority().certificate)
