from __future__ import annotations

import asyncio
import hashlib
from typing import TYPE_CHECKING

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_clients import connected_client
from xtr_mailer.exception import TransportError, UnexpectedResponseError
from xtr_mailer.transport.smtp._smtp_client import SmtpClient
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig as Config

if TYPE_CHECKING:
    from tests.support.certificates import Certificate

pytestmark = pytest.mark.anyio


# STARTTLS


async def test_starttls_switches_the_connection_to_tls(certificate: Certificate) -> None:
    async with ScriptedSmtpServer(tls_context=certificate.server_context()) as server:
        server.capabilities = ["STARTTLS"]
        client = SmtpClient(
            Config("localhost", server.port, validate_certs=False, local_hostname="client.example")
        )
        _ = await client.connect()
        _ = await client.ehlo()

        await client.starttls()
        _ = await client.ehlo()
        capabilities = client.capabilities
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
        client = await connected_client(server)
        _ = await client.ehlo()

        with pytest.raises(TransportError, match="STARTTLS"):
            await client.starttls()
        client.close()


async def test_a_refused_starttls_raises_with_the_reply_code() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["STARTTLS"]
        server.replies["STARTTLS"] = ["454 4.7.0 TLS not available"]
        client = await connected_client(server)
        _ = await client.ehlo()

        with pytest.raises(UnexpectedResponseError) as caught:
            await client.starttls()
        client.close()

    assert caught.value.code == 454
    assert str(caught.value).startswith('Expected response code "220" but got code "454"')


# Implicit TLS


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


# Peer fingerprint


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
        f'Connection to "ssl://localhost:{port}" has been closed unexpectedly.',
    }
