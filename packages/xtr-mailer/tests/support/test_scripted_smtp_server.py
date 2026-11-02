"""The scripted server speaks SMTP the way the client tests rely on."""

from __future__ import annotations

import asyncio
import ssl
from typing import TYPE_CHECKING

import pytest

from tests.support.certificates import make_certificate
from tests.support.scripted_smtp_server import STALL, ScriptedSmtpServer

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


async def _talk(
    server: ScriptedSmtpServer, *lines: str
) -> tuple[list[str], asyncio.StreamReader, asyncio.StreamWriter]:
    reader, writer = await asyncio.open_connection(server.host, server.port)
    replies = [await _reply(reader)]
    for line in lines:
        writer.write(line.encode() + b"\r\n")
        await writer.drain()
        replies.append(await _reply(reader))
    return replies, reader, writer


async def _reply(reader: asyncio.StreamReader) -> str:
    lines: list[str] = []
    while True:
        line = (await reader.readline()).decode().rstrip("\r\n")
        lines.append(line)
        if line[3:4] != "-":
            return "\n".join(lines)


async def test_it_greets_and_advertises_its_capabilities() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["STARTTLS", "AUTH PLAIN"]
        replies, _, writer = await _talk(server, "EHLO client")
        writer.close()

    assert replies == [
        "220 localhost ESMTP ready",
        "250-localhost\n250-STARTTLS\n250 AUTH PLAIN",
    ]
    assert server.commands == ["EHLO client"]
    assert server.peers == ["127.0.0.1"]


async def test_a_scripted_reply_is_used_once() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["421 closing"]
        replies, _, writer = await _talk(server, "NOOP", "NOOP", "BOGUS")
        writer.close()

    assert replies[1:] == ["421 closing", "250 2.0.0 Ok", "500 5.5.2 Command not recognized"]


async def test_it_records_a_message_without_its_dot_stuffing() -> None:
    async with ScriptedSmtpServer() as server:
        replies, reader, writer = await _talk(server, "DATA")
        writer.write(b"Subject: hi\r\n\r\n..dot\r\n.\r\n")
        await writer.drain()
        replies.append(await _reply(reader))
        writer.close()

    assert replies[1:] == [
        '354 End data with "." on a line by itself',
        "250 2.0.0 Ok: queued as 1A2B3C",
    ]
    assert server.messages == [b"Subject: hi\r\n\r\n.dot\r\n"]


async def test_it_answers_an_auth_exchange_from_the_auth_script() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["AUTH"] = ["334 VXNlcm5hbWU6", "535 no"]
        replies, _, writer = await _talk(server, "AUTH LOGIN", "dXNlcg==", "NOOP")
        writer.close()

    assert replies[1:] == ["334 VXNlcm5hbWU6", "535 no", "250 2.0.0 Ok"]


async def test_it_drops_the_connection_at_a_dropped_verb() -> None:
    async with ScriptedSmtpServer() as server:
        server.drop.add("MAIL")
        reader, writer = await asyncio.open_connection(server.host, server.port)
        _ = await _reply(reader)
        writer.write(b"MAIL FROM:<a@example.com>\r\n")
        rest = await reader.read()
        writer.close()

    assert rest == b""


async def test_a_silent_server_never_greets() -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = None
        reader, writer = await asyncio.open_connection(server.host, server.port)
        with pytest.raises(TimeoutError):
            _ = await asyncio.wait_for(reader.readline(), 0.05)
        writer.close()


async def test_a_stalled_verb_is_never_answered() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("NOOP")
        reader, writer = await asyncio.open_connection(server.host, server.port)
        _ = await _reply(reader)
        writer.write(b"NOOP\r\n")
        with pytest.raises(TimeoutError):
            _ = await asyncio.wait_for(reader.readline(), 0.05)
        writer.close()


async def test_a_stalled_message_is_recorded_but_never_answered() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("DATA_END")
        _, reader, writer = await _talk(server, "DATA")
        writer.write(b"body\r\n.\r\n")
        with pytest.raises(TimeoutError):
            _ = await asyncio.wait_for(reader.readline(), 0.05)
        writer.close()

    assert server.messages == [b"body\r\n"]


async def test_a_scripted_stall_silences_the_server_at_that_line() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["AUTH"] = ["334 VXNlcm5hbWU6", STALL]
        _, reader, writer = await _talk(server, "AUTH LOGIN")
        writer.write(b"dXNlcg==\r\n")
        with pytest.raises(TimeoutError):
            _ = await asyncio.wait_for(reader.readline(), 0.05)
        writer.close()

    assert server.commands == ["AUTH LOGIN", "dXNlcg=="]


async def test_a_reply_s_surrogates_go_out_as_raw_bytes() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["250 caf\udce9"]
        reader, writer = await asyncio.open_connection(server.host, server.port)
        _ = await _reply(reader)
        writer.write(b"NOOP\r\n")
        line = await reader.readline()
        writer.close()

    assert line == b"250 caf\xe9\r\n"


async def test_it_switches_to_tls_after_starttls(tmp_path: Path) -> None:
    certificate = make_certificate(tmp_path)
    client_context = ssl.create_default_context(cafile=certificate.cert_path)
    async with ScriptedSmtpServer(tls_context=certificate.server_context()) as server:
        replies, reader, writer = await _talk(server, "STARTTLS")
        await writer.start_tls(client_context, server_hostname="localhost")
        writer.write(b"NOOP\r\n")
        await writer.drain()
        replies.append(await _reply(reader))
        writer.close()

    assert replies[1:] == ["220 2.0.0 Ready to start TLS", "250 2.0.0 Ok"]
    assert server.tls_upgrades == 1


async def test_it_can_speak_tls_from_the_first_byte(tmp_path: Path) -> None:
    certificate = make_certificate(tmp_path)
    client_context = ssl.create_default_context(cafile=certificate.cert_path)
    async with ScriptedSmtpServer(
        tls_context=certificate.server_context(), implicit_tls=True
    ) as server:
        reader, writer = await asyncio.open_connection(
            server.host, server.port, ssl=client_context, server_hostname="localhost"
        )
        greeting = await _reply(reader)
        writer.close()

    assert greeting == "220 localhost ESMTP ready"
