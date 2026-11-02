"""A signed email handed to a provider's API: DKIM keeps its fields, S/MIME is refused."""

from __future__ import annotations

from functools import cache
from typing import TYPE_CHECKING

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from typing_extensions import override
from xtr_http_client import MockHttpClient
from xtr_mime import Email, MimeRuntimeError
from xtr_mime.crypto import DkimSigner, SMimeSigner

from tests.support.certificates import make_certificate
from xtr_mailer import MailerRuntimeError
from xtr_mailer.transport import AbstractApiTransport

if TYPE_CHECKING:
    from pathlib import Path

    from xtr_http_client_contracts import HttpResponseInterface

    from xtr_mailer import Envelope, SentMessage

pytestmark = pytest.mark.anyio


class _ApiTransport(AbstractApiTransport):
    """Keeps the email each call was built from."""

    def __init__(self) -> None:
        super().__init__(MockHttpClient())
        self.emails: list[Email] = []

    @override
    async def _do_send_api(
        self, sent_message: SentMessage, email: Email, envelope: Envelope
    ) -> HttpResponseInterface:
        self.emails.append(email)
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
