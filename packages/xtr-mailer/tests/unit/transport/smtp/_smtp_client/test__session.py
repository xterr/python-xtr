from __future__ import annotations

import asyncio
from typing import NoReturn

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from xtr_mailer.exception import InvalidArgumentError, TransportError
from xtr_mailer.transport.smtp._smtp_client import SmtpClient
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig as Config


@pytest.mark.anyio
async def test_the_connection_binds_to_the_source_address() -> None:
    async with ScriptedSmtpServer() as server:
        client = SmtpClient(Config(server.host, server.port, source_address="127.0.0.1"))

        _ = await client.connect()
        client.close()

    assert server.peers == ["127.0.0.1"]


def test_a_local_hostname_with_whitespace_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = SmtpClient(Config(local_hostname="bad host"))


@pytest.mark.anyio
@pytest.mark.parametrize(
    "refusal", [UnicodeError("encoding with 'idna' codec failed"), ValueError("bad name")]
)
async def test_a_resolver_refusing_the_host_is_a_transport_error(
    monkeypatch: pytest.MonkeyPatch, refusal: ValueError
) -> None:
    async def refuse(*arguments: object, **options: object) -> NoReturn:
        del arguments, options
        raise refusal

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", refuse)
    client = SmtpClient(Config("mail.example.com", 2525, timeout=2.0))

    with pytest.raises(TransportError) as caught:
        _ = await client.connect()

    assert str(caught.value) == (
        'Connection could not be established with host "mail.example.com:2525": '
        "the resolver cannot look the host name up."
    )
    assert caught.value.__context__ is None
    assert not client.is_connected
