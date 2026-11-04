"""A DKIM-signed email piped to sendmail arrives with the body it was signed with."""

from __future__ import annotations

import base64
from functools import cache
from typing import TYPE_CHECKING

import dkim
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from xtr_mime import Address, Email
from xtr_mime.crypto import DkimOptions, DkimSigner

from tests.support.sendmail_fakes import FakeSendmail, fake_command
from xtr_mailer import Envelope
from xtr_mailer.transport import SendmailTransport

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


@cache
def _key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _pem() -> str:
    return (
        _key()
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        .decode("ascii")
    )


def _published_key(name: bytes, timeout: int = 5) -> bytes | None:
    """Answer the TXT query for ``default._domainkey.example.com.``, as DNS would."""
    del timeout
    if name != b"default._domainkey.example.com.":
        return None
    public = (
        _key()
        .public_key()
        .public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return b"v=DKIM1; k=rsa; p=" + base64.b64encode(public)


async def test_a_body_with_lines_starting_with_a_dot_verifies_as_received(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    email = (
        Email()
        .from_("from@example.com")
        .to("to@example.com")
        .subject("Dots")
        .text(".one dot\n..two dots\n.\nend")
    )
    options = DkimOptions().header_canon("simple").body_canon("simple")
    signed = DkimSigner(_pem(), "example.com", "default").sign(email, options)
    envelope = Envelope(Address("from@example.com"), [Address("to@example.com")])

    _ = await SendmailTransport(fake_command("-t")).send(signed, envelope)

    # The program stores what it reads with CRLF line endings, as an MTA does.
    received = fake.input.replace(b"\n", b"\r\n")
    assert b"\r\n.one dot\r\n..two dots\r\n.\r\nend" in received
    assert dkim.verify(received, dnsfunc=_published_key)
