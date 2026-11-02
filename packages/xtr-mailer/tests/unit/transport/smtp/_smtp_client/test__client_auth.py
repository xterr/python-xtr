"""How an SMTP client keeps the credentials of an ``AUTH`` exchange out of what it shows."""

from __future__ import annotations

import base64

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_clients import connected_client
from xtr_mailer.exception import UnexpectedResponseError

pytestmark = pytest.mark.anyio


async def test_an_auth_exchange_is_kept_out_of_the_debug_transcript() -> None:
    user = base64.b64encode(b"user").decode()
    password = base64.b64encode(b"s3cret").decode()
    async with ScriptedSmtpServer() as server:
        server.replies["AUTH"] = [
            "334 VXNlcm5hbWU6",
            "334 UGFzc3dvcmQ6",
            "535 5.7.8 Bad credentials",
        ]
        client = await connected_client(server)
        _ = await client.execute("AUTH LOGIN", [334])
        _ = await client.execute(user, [334])

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute(password, [235])
        client.close()

    assert server.commands == ["AUTH LOGIN", user, password]
    assert caught.value.debug == "> [redacted]\n< 535 5.7.8 Bad credentials\n"
    assert password not in str(caught.value)


async def test_an_auth_command_carrying_its_credentials_is_redacted() -> None:
    payload = base64.b64encode(b"\0user\0s3cret").decode()
    async with ScriptedSmtpServer() as server:
        server.replies["AUTH"] = ["535 5.7.8 Bad credentials"]
        client = await connected_client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute(f"AUTH PLAIN {payload}", [235])
        client.close()

    assert caught.value.debug == "> AUTH PLAIN [redacted]\n< 535 5.7.8 Bad credentials\n"


async def test_commands_after_an_auth_exchange_are_not_redacted() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["MAIL"] = ["550 no"]
        client = await connected_client(server)
        _ = await client.execute("AUTH PLAIN AHVzZXIAcw==", [235])

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("MAIL FROM:<sender@example.com>", [250])
        client.close()

    assert caught.value.debug.startswith("> MAIL FROM:<sender@example.com>\n")


async def test_a_password_the_server_echoes_is_scrubbed_from_the_refusal() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["AUTH"] = ["535 5.7.8 Bad password s3cret for AHVzZXIAczNjcmV0"]
        client = await connected_client(server)
        client.conceal("s3cret")

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute("AUTH PLAIN AHVzZXIAczNjcmV0", [235])
        client.close()

    assert "s3cret" not in str(caught.value)
    assert "AHVzZXIAczNjcmV0" not in str(caught.value)
    assert caught.value.debug == (
        "> AUTH PLAIN [redacted]\n< 535 5.7.8 Bad password [redacted] for [redacted]\n"
    )
