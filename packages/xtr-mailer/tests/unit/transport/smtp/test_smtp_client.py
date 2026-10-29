from __future__ import annotations

import asyncio
import base64
import hashlib
import socket
import struct
from typing import TYPE_CHECKING

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from xtr_mailer.exception import (
    InvalidArgumentError,
    LogicError,
    TransportError,
    UnexpectedResponseError,
)
from xtr_mailer.transport.smtp._smtp_client import SmtpClient
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig as Config

if TYPE_CHECKING:
    from tests.support.certificates import Certificate

pytestmark = pytest.mark.anyio


def _client(server: ScriptedSmtpServer, *, timeout: float = 2.0) -> SmtpClient:
    return SmtpClient(
        Config(server.host, server.port, timeout=timeout, local_hostname="client.example")
    )


async def _connected(server: ScriptedSmtpServer) -> SmtpClient:
    client = _client(server)
    _ = await client.connect()
    return client


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed


# Sessions


async def test_connect_returns_the_greeting() -> None:
    async with ScriptedSmtpServer() as server:
        client = _client(server)

        greeting = await client.connect()

        assert greeting == "220 localhost ESMTP ready"
        assert client.is_connected
        assert not client.uses_tls
        client.close()


async def test_ehlo_names_the_local_hostname_and_returns_the_capabilities() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["STARTTLS", "AUTH PLAIN login", "SIZE=1000", "BAD_EXT", "8BITMIME"]
        client = await _connected(server)

        capabilities = await client.ehlo()

        assert client.supports_extension("starttls")
        assert not client.supports_extension("SMTPUTF8")
        client.close()

    assert server.commands == ["EHLO client.example"]
    assert capabilities == {
        "STARTTLS": [],
        "AUTH": ["PLAIN", "LOGIN"],
        "SIZE": ["1000"],
        "8BITMIME": [],
    }


async def test_helo_names_the_local_hostname() -> None:
    async with ScriptedSmtpServer() as server:
        client = await _connected(server)

        reply = await client.helo()
        client.close()

    assert reply == "250 localhost"
    assert server.commands == ["HELO client.example"]


async def test_connecting_again_starts_a_new_session() -> None:
    async with ScriptedSmtpServer() as server:
        client = await _connected(server)
        _ = await client.ehlo()

        _ = await client.connect()

        assert not client.supports_extension("PIPELINING")
        assert client.is_connected
        await client.quit()

    assert len(server.peers) == 2


async def test_a_message_is_handed_over_with_its_leading_periods_stuffed() -> None:
    async with ScriptedSmtpServer() as server:
        client = await _connected(server)
        _ = await client.ehlo()

        _ = await client.mail_from("sender@example.com", ["SMTPUTF8"])
        _ = await client.rcpt_to("rcpt@example.com")
        reply = await client.data(b"Subject: hi\r\n\r\n.leading\nbare")
        await client.quit()

    assert reply == "250 2.0.0 Ok: queued as 1A2B3C"
    assert server.commands[1:3] == [
        "MAIL FROM:<sender@example.com> SMTPUTF8",
        "RCPT TO:<rcpt@example.com>",
    ]
    assert server.commands[-1] == "QUIT"
    assert server.messages == [b"Subject: hi\r\n\r\n.leading\r\nbare\r\n"]
    assert not client.is_connected


async def test_a_recipient_the_server_cannot_verify_is_accepted() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["RCPT"] = ["252 2.1.5 Cannot verify"]
        client = await _connected(server)

        reply = await client.rcpt_to("rcpt@example.com")
        client.close()

    assert reply == "252 2.1.5 Cannot verify"


async def test_rset_and_noop_return_their_replies() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["250 2.0.0 I am here"]
        client = await _connected(server)

        replies = [await client.rset(), await client.noop()]
        client.close()

    assert replies == ["250 2.0.0 Ok", "250 2.0.0 I am here"]
    assert server.commands == ["RSET", "NOOP"]


async def test_execute_sends_a_raw_command_and_returns_a_multiline_reply_whole() -> None:
    async with ScriptedSmtpServer() as server:
        client = await _connected(server)

        reply = await client.execute("EHLO raw.example", [250])
        client.close()

    assert reply == "250-localhost\r\n250-PIPELINING\r\n250 8BITMIME"


async def test_the_connection_binds_to_the_source_address() -> None:
    async with ScriptedSmtpServer() as server:
        client = SmtpClient(Config(server.host, server.port, source_address="127.0.0.1"))

        _ = await client.connect()
        client.close()

    assert server.peers == ["127.0.0.1"]


# Refusals


async def test_a_refused_command_raises_with_the_reply_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["MAIL"] = ["550 5.7.1 Sender denied"]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.mail_from("sender@example.com")
        client.close()

    assert str(caught.value) == (
        'Expected response code "250" but got code "550", with message "550 5.7.1 Sender denied".'
    )
    assert caught.value.code == 550
    assert caught.value.debug == "> MAIL FROM:<sender@example.com>\n< 550 5.7.1 Sender denied\n"


async def test_every_accepted_code_is_named_in_a_refusal() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["RCPT"] = ["554 no"]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError, match='code "250/251/252" but got code "554"'):
            _ = await client.rcpt_to("rcpt@example.com")
        client.close()


async def test_a_refused_greeting_raises_with_the_reply_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = "554 5.3.2 Go away"
        client = _client(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.connect()

    assert str(caught.value) == (
        'Expected response code "220" but got code "554", with message "554 5.3.2 Go away".'
    )
    assert caught.value.code == 554
    assert not client.is_connected


async def test_a_refused_ehlo_raises_with_the_reply_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["EHLO"] = ["502 5.5.1 EHLO not implemented"]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.ehlo()
        client.close()

    assert caught.value.code == 502
    assert caught.value.debug == "> EHLO client.example\n< 502 5.5.1 EHLO not implemented\n"


async def test_a_refused_helo_raises_with_the_reply_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["HELO"] = ["501 5.5.4 Syntax error"]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError, match='"250" but got code "501"'):
            _ = await client.helo()
        client.close()


async def test_a_malformed_reply_is_an_empty_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["garbage"]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.noop()
        client.close()

    assert str(caught.value).startswith('Expected response code "250" but got empty code, with')
    assert caught.value.code == 0


async def test_a_malformed_reply_is_named_by_its_own_text_trimmed() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["  hello there  "]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.noop()
        client.close()

    assert str(caught.value) == (
        'Expected response code "250" but got empty code, with message "hello there".'
    )
    assert caught.value.debug == "> NOOP\n< hello there\n"


async def test_a_reply_too_long_to_read_is_an_empty_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["250 " + "x" * 9000]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.noop()
        client.close()

    assert str(caught.value) == (
        'Expected response code "250" but got empty code, with message "Response too long".'
    )
    assert caught.value.code == 0
    assert caught.value.debug == "> NOOP\n< Response too long\n"


async def test_a_blank_reply_adds_no_empty_debug_line() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["NOOP"] = ["   "]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.noop()
        client.close()

    assert str(caught.value) == 'Expected response code "250" but got empty code.'
    assert caught.value.debug == "> NOOP\n"


async def test_a_refused_data_command_names_the_start_of_input_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["DATA"] = ["554 5.5.1 No valid recipients"]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError, match='"354" but got code "554"'):
            _ = await client.data(b"Subject: hi\r\n\r\nbody\r\n")
        client.close()


async def test_a_refused_message_names_the_completion_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["DATA_END"] = ["552 5.3.4 Message too big"]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.data(b"Subject: hi\r\n\r\nbody\r\n")
        client.close()

    assert caught.value.code == 552
    assert caught.value.debug == "> [message]\n< 552 5.3.4 Message too big\n"


async def test_a_closing_server_ends_the_connection() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["DATA_END"] = ["421 4.3.2 Shutting down"]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError):
            _ = await client.data(b"Subject: hi\r\n\r\nbody\r\n")

    assert not client.is_connected


async def test_a_refused_quit_still_closes_the_connection() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["QUIT"] = ["500 what"]
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError):
            await client.quit()

    assert not client.is_connected


# Broken connections


async def test_a_refused_connection_raises_a_transport_error() -> None:
    port = _free_port()
    client = SmtpClient(Config("127.0.0.1", port, timeout=1.0))

    with pytest.raises(TransportError) as caught:
        _ = await client.connect()

    assert str(caught.value).startswith(
        f'Connection could not be established with host "127.0.0.1:{port}": '
    )
    assert caught.value.code == 0
    assert not client.is_connected


async def test_a_server_that_never_greets_times_out() -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = None
        client = _client(server, timeout=0.1)

        with pytest.raises(TransportError) as caught:
            _ = await client.connect()

    assert str(caught.value) == f'Connection to "127.0.0.1:{server.port}" timed out.'


async def test_a_command_that_is_never_answered_times_out_and_closes() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("NOOP")
        client = _client(server, timeout=0.1)
        _ = await client.connect()

        with pytest.raises(TransportError) as caught:
            _ = await client.noop()

    assert str(caught.value) == f'Connection to "127.0.0.1:{server.port}" timed out.'
    assert caught.value.debug == "> NOOP\n"
    assert not client.is_connected


async def test_a_server_that_hangs_up_mid_session_raises_a_transport_error() -> None:
    async with ScriptedSmtpServer() as server:
        server.drop.add("MAIL")
        client = await _connected(server)

        with pytest.raises(TransportError) as caught:
            _ = await client.mail_from("sender@example.com")

    assert str(caught.value) == (
        f'Connection to "127.0.0.1:{server.port}" has been closed unexpectedly.'
    )
    assert not client.is_connected


async def test_a_message_that_is_never_accepted_times_out_and_closes() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("DATA_END")
        client = _client(server, timeout=0.1)
        _ = await client.connect()

        with pytest.raises(TransportError) as caught:
            _ = await client.data(b"Subject: hi\r\n\r\nbody\r\n")

    assert str(caught.value) == f'Connection to "127.0.0.1:{server.port}" timed out.'
    assert caught.value.debug == "> [message]\n"
    assert not client.is_connected


async def test_a_slow_server_still_reading_a_large_message_does_not_time_out() -> None:
    line = b"x" * 1022 + b"\r\n"
    message = line * 4096
    async with ScriptedSmtpServer() as server:
        # About 3 MB/s: the 4 MiB upload outlasts the timeout, while what the buffers
        # still hold after the last write is read well within it.
        server.throttle = (32 * 1024, 0.01)
        client = _client(server, timeout=1.0)
        _ = await client.connect()
        # A small send buffer too, so the upload's pace is the server's, not the kernel's.
        sock: socket.socket = client._smtp.get_transport_info("socket")  # pyright: ignore[reportAny] — aiosmtplib types transport info as Any
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 32 * 1024)

        started = asyncio.get_running_loop().time()
        reply = await client.data(message)
        elapsed = asyncio.get_running_loop().time() - started
        client.close()

    assert reply == "250 2.0.0 Ok: queued as 1A2B3C"
    assert server.messages == [message]
    assert elapsed > 1.0  # the whole upload outlasted the timeout, each write did not


async def test_a_server_that_stops_reading_a_message_times_out_and_closes() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("DATA_BODY")
        client = _client(server, timeout=0.2)
        _ = await client.connect()

        with pytest.raises(TransportError) as caught:
            _ = await client.data(b"x" * (16 * 1024 * 1024))

    assert str(caught.value) == f'Connection to "127.0.0.1:{server.port}" timed out.'
    assert caught.value.debug == "> [message]\n"
    assert not client.is_connected


async def test_a_server_that_resets_the_connection_mid_message_raises_a_transport_error() -> None:
    async def reset_at_data(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 localhost ESMTP ready\r\n")
        _ = await reader.readline()
        writer.write(b'354 End data with "." on a line by itself\r\n')
        await writer.drain()
        await asyncio.sleep(0.05)
        sock: socket.socket = writer.get_extra_info("socket")  # pyright: ignore[reportAny] — get_extra_info() is Any in typeshed
        # A zero linger turns the close into a reset, as a crashing server's would be.
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        writer.transport.abort()

    server = await asyncio.start_server(reset_at_data, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed
    client = SmtpClient(Config("127.0.0.1", port, timeout=2.0))
    _ = await client.connect()

    with pytest.raises(TransportError) as caught:
        _ = await client.data(b"x" * (16 * 1024 * 1024))
    server.close()
    await server.wait_closed()

    assert str(caught.value) == f'Connection to "127.0.0.1:{port}" has been closed unexpectedly.'
    assert not client.is_connected


async def test_a_server_that_hangs_up_before_greeting_raises_a_transport_error() -> None:
    def hang_up(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.close()

    server = await asyncio.start_server(hang_up, "127.0.0.1", 0)
    port = int(server.sockets[0].getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed
    client = SmtpClient(Config("127.0.0.1", port))

    with pytest.raises(TransportError) as caught:
        _ = await client.connect()
    server.close()
    await server.wait_closed()

    assert str(caught.value) == f'Connection to "127.0.0.1:{port}" has been closed unexpectedly.'


async def test_a_message_sent_without_a_connection_raises_a_transport_error() -> None:
    client = SmtpClient(Config("127.0.0.1", 2525))

    with pytest.raises(TransportError, match="has been closed unexpectedly"):
        _ = await client.data(b"x")


async def test_a_command_sent_without_a_connection_raises_a_transport_error() -> None:
    client = SmtpClient(Config("127.0.0.1", 2525))

    with pytest.raises(TransportError, match="has been closed unexpectedly"):
        _ = await client.noop()


# Authentication


async def test_an_auth_exchange_is_kept_out_of_the_debug_transcript() -> None:
    user = base64.b64encode(b"user").decode()
    password = base64.b64encode(b"s3cret").decode()
    async with ScriptedSmtpServer() as server:
        server.replies["AUTH"] = [
            "334 VXNlcm5hbWU6",
            "334 UGFzc3dvcmQ6",
            "535 5.7.8 Bad credentials",
        ]
        client = await _connected(server)
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
        client = await _connected(server)

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.execute(f"AUTH PLAIN {payload}", [235])
        client.close()

    assert caught.value.debug == "> AUTH PLAIN [redacted]\n< 535 5.7.8 Bad credentials\n"


async def test_commands_after_an_auth_exchange_are_not_redacted() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["MAIL"] = ["550 no"]
        client = await _connected(server)
        _ = await client.execute("AUTH PLAIN AHVzZXIAcw==", [235])

        with pytest.raises(UnexpectedResponseError) as caught:
            _ = await client.mail_from("sender@example.com")
        client.close()

    assert caught.value.debug.startswith("> MAIL FROM:<sender@example.com>\n")


# Arguments


async def test_a_command_with_a_line_break_is_refused() -> None:
    async with ScriptedSmtpServer() as server:
        client = await _connected(server)

        with pytest.raises(InvalidArgumentError):
            _ = await client.execute("NOOP\r\nRSET", [250])
        client.close()

    assert server.commands == []


def test_a_local_hostname_with_whitespace_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = SmtpClient(Config(local_hostname="bad host"))


async def test_a_command_must_accept_some_code() -> None:
    client = SmtpClient(Config())

    with pytest.raises(LogicError, match=r"^You must set the expected response code\.$"):
        _ = await client.execute("NOOP", [])


def test_its_description_names_the_server() -> None:
    assert SmtpClient(Config("mail.example.com", 465, tls=True)).description == (
        "ssl://mail.example.com:465"
    )


# TLS


async def test_starttls_switches_the_connection_to_tls(certificate: Certificate) -> None:
    async with ScriptedSmtpServer(tls_context=certificate.server_context()) as server:
        server.capabilities = ["STARTTLS"]
        client = SmtpClient(
            Config("localhost", server.port, validate_certs=False, local_hostname="client.example")
        )
        _ = await client.connect()
        _ = await client.ehlo()

        await client.starttls()
        capabilities = await client.ehlo()
        client.close()

    assert server.tls_upgrades == 1
    assert capabilities == {"STARTTLS": []}
    assert server.commands == ["EHLO client.example", "STARTTLS", "EHLO client.example"]


async def test_starttls_reports_tls_while_connected(certificate: Certificate) -> None:
    async with ScriptedSmtpServer(tls_context=certificate.server_context()) as server:
        server.capabilities = ["STARTTLS"]
        client = SmtpClient(Config("localhost", server.port, validate_certs=False))
        _ = await client.connect()
        _ = await client.ehlo()

        await client.starttls()

        assert client.uses_tls
        client.close()
        assert not client.uses_tls


async def test_starttls_refuses_a_certificate_it_cannot_verify(certificate: Certificate) -> None:
    async with ScriptedSmtpServer(tls_context=certificate.server_context()) as server:
        server.capabilities = ["STARTTLS"]
        client = SmtpClient(Config("localhost", server.port))
        _ = await client.connect()
        _ = await client.ehlo()

        with pytest.raises(TransportError, match=r"^Unable to connect with STARTTLS: "):
            await client.starttls()
        client.close()


async def test_starttls_needs_the_server_to_offer_it() -> None:
    async with ScriptedSmtpServer() as server:
        client = await _connected(server)
        _ = await client.ehlo()

        with pytest.raises(TransportError, match="STARTTLS"):
            await client.starttls()
        client.close()


async def test_a_refused_starttls_raises_with_the_reply_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["STARTTLS"]
        server.replies["STARTTLS"] = ["454 4.7.0 TLS not available"]
        client = await _connected(server)
        _ = await client.ehlo()

        with pytest.raises(UnexpectedResponseError) as caught:
            await client.starttls()
        client.close()

    assert caught.value.code == 454
    assert str(caught.value).startswith('Expected response code "220" but got code "454"')


async def test_an_implicit_tls_connection_is_encrypted_from_the_start(
    certificate: Certificate,
) -> None:
    async with ScriptedSmtpServer(
        tls_context=certificate.server_context(), implicit_tls=True
    ) as server:
        client = SmtpClient(Config("localhost", server.port, tls=True, validate_certs=False))

        greeting = await client.connect()

        assert greeting == "220 localhost ESMTP ready"
        assert client.uses_tls
        client.close()


async def test_an_implicit_tls_connection_verifies_the_certificate(
    certificate: Certificate,
) -> None:
    async with ScriptedSmtpServer(
        tls_context=certificate.server_context(), implicit_tls=True
    ) as server:
        client = SmtpClient(Config("localhost", server.port, tls=True))

        with pytest.raises(TransportError) as caught:
            _ = await client.connect()

    assert str(caught.value).startswith(
        f'Connection could not be established with host "ssl://localhost:{server.port}": '
    )


async def test_an_implicit_tls_handshake_that_never_completes_times_out() -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = None
        client = SmtpClient(Config(server.host, server.port, tls=True, timeout=0.1))

        with pytest.raises(TransportError, match=r"^Connection could not be established with"):
            _ = await client.connect()


@pytest.mark.parametrize("algorithm", ["md5", "sha1", "sha256"])
async def test_a_matching_peer_fingerprint_is_accepted(
    certificate: Certificate, algorithm: str
) -> None:
    fingerprint = hashlib.new(algorithm, certificate.der).hexdigest().upper()
    async with ScriptedSmtpServer(
        tls_context=certificate.server_context(), implicit_tls=True
    ) as server:
        client = SmtpClient(
            Config(
                "localhost",
                server.port,
                tls=True,
                validate_certs=False,
                peer_fingerprint=fingerprint,
            )
        )

        _ = await client.connect()

        assert client.is_connected
        client.close()


async def test_a_mismatching_peer_fingerprint_is_refused(certificate: Certificate) -> None:
    async with ScriptedSmtpServer(
        tls_context=certificate.server_context(), implicit_tls=True
    ) as server:
        client = SmtpClient(
            Config(
                "localhost", server.port, tls=True, validate_certs=False, peer_fingerprint="0" * 40
            )
        )

        with pytest.raises(TransportError) as caught:
            _ = await client.connect()

    assert str(caught.value) == (
        f'Connection could not be established with host "ssl://localhost:{server.port}": '
        "peer fingerprint match failure"
    )
    assert not client.is_connected


async def test_a_mismatching_peer_fingerprint_after_starttls_is_refused(
    certificate: Certificate,
) -> None:
    async with ScriptedSmtpServer(tls_context=certificate.server_context()) as server:
        server.capabilities = ["STARTTLS"]
        client = SmtpClient(
            Config("localhost", server.port, validate_certs=False, peer_fingerprint="0" * 64)
        )
        _ = await client.connect()
        _ = await client.ehlo()

        with pytest.raises(
            TransportError,
            match=r"^Unable to connect with STARTTLS: peer fingerprint match failure$",
        ):
            await client.starttls()

    assert not client.is_connected


async def test_a_peer_fingerprint_is_not_checked_on_a_plain_connection() -> None:
    async with ScriptedSmtpServer() as server:
        client = SmtpClient(Config(server.host, server.port, peer_fingerprint="0" * 32))

        _ = await client.connect()

        assert client.is_connected
        client.close()


async def test_a_tls_server_that_hangs_up_before_its_fingerprint_is_read_raises_a_transport_error(
    certificate: Certificate,
) -> None:
    def greet_and_hang_up(_reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        writer.write(b"220 localhost ESMTP ready\r\n")
        writer.close()

    server = await asyncio.start_server(
        greet_and_hang_up, "127.0.0.1", 0, ssl=certificate.server_context()
    )
    port = int(server.sockets[0].getsockname()[1])  # pyright: ignore[reportAny] — getsockname() is Any in typeshed
    fingerprint = hashlib.sha256(certificate.der).hexdigest()
    client = SmtpClient(
        Config("localhost", port, tls=True, validate_certs=False, peer_fingerprint=fingerprint)
    )
    failures: list[str] = []

    # The hang-up races the fingerprint read; enough attempts make it lose at least once.
    for _ in range(30):
        try:
            _ = await client.connect()
        except TransportError as error:
            failures.append(str(error))
        client.close()
    server.close()
    await server.wait_closed()

    assert failures
    assert set(failures) == {
        (
            f'Connection could not be established with host "ssl://localhost:{port}": '
            "peer fingerprint match failure"
        )
    }
