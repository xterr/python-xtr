"""An email sent end to end: STARTTLS, AUTH PLAIN, and the very bytes rendered received."""

from __future__ import annotations

import base64
import hashlib
from typing import TYPE_CHECKING

import pytest
from xtr_mime import Email

from tests.support.certificates import make_certificate
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from xtr_mailer.transport.smtp import EsmtpTransport

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


async def test_an_email_reaches_the_server_over_starttls_after_auth_plain(tmp_path: Path) -> None:
    certificate = make_certificate(tmp_path)
    message = (
        Email()
        .from_("Fabien <fabien@example.com>")
        .to("helene@example.com")
        .subject("Über alles")
        .text("Line one\n.Line starting with a period\nLine three")
        .html("<p>Hello</p>")
    )
    async with ScriptedSmtpServer(tls_context=certificate.server_context()) as server:
        server.capabilities = ["STARTTLS", "AUTH PLAIN LOGIN", "8BITMIME"]
        transport = (
            EsmtpTransport("localhost", server.port)
            .set_verify_peer(False)
            .set_peer_fingerprint(hashlib.sha256(certificate.der).hexdigest())
            .set_timeout(5.0)
            .set_username("mailer")
            .set_password("p4ssw0rd")
            .set_local_domain("client.example.com")
        )

        sent = await transport.send(message)
        await transport.stop()

    assert sent is not None
    assert server.tls_upgrades == 1
    auth = next(command for command in server.commands if command.startswith("AUTH "))
    assert server.commands.index("STARTTLS") < server.commands.index(auth)
    assert base64.b64decode(auth.removeprefix("AUTH PLAIN ")) == b"mailer\0mailer\0p4ssw0rd"
    assert server.commands[-1] == "QUIT"
    assert server.messages == [b"".join(sent.to_iterable())]
