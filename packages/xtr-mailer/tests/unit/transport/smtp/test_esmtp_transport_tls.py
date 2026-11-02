"""TLS on an ESMTP session: switched to when offered, required when asked, never redone."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_sends import email, esmtp_transport
from xtr_mailer.exception import TransportError
from xtr_mailer.transport.smtp import EsmtpTransport

if TYPE_CHECKING:
    from tests.support.certificates import Certificate

pytestmark = pytest.mark.anyio


def _starttls_server(certificate: Certificate) -> ScriptedSmtpServer:
    server = ScriptedSmtpServer(tls_context=certificate.server_context())
    server.capabilities = ["STARTTLS"]
    return server


def _trusting(server: ScriptedSmtpServer) -> EsmtpTransport:
    return esmtp_transport(server, host="localhost").set_verify_peer(False)


async def test_starttls_is_used_when_the_server_offers_it(certificate: Certificate) -> None:
    async with _starttls_server(certificate) as server:
        _ = await _trusting(server).send(email())

    assert server.tls_upgrades == 1
    assert server.commands[:4] == [
        "EHLO [127.0.0.1]",
        "STARTTLS",
        "EHLO [127.0.0.1]",
        "MAIL FROM:<sender@example.org>",
    ]


async def test_starttls_is_not_used_when_auto_tls_is_off(certificate: Certificate) -> None:
    async with _starttls_server(certificate) as server:
        _ = await _trusting(server).set_auto_tls(False).send(email())

    assert server.tls_upgrades == 0
    assert "STARTTLS" not in server.commands


async def test_required_tls_is_met_by_starttls(certificate: Certificate) -> None:
    async with _starttls_server(certificate) as server:
        _ = await _trusting(server).set_require_tls(True).send(email())

    assert server.tls_upgrades == 1


async def test_required_tls_without_auto_tls_is_refused(certificate: Certificate) -> None:
    async with _starttls_server(certificate) as server:
        transport = _trusting(server).set_auto_tls(False).set_require_tls(True)

        with pytest.raises(TransportError, match=r"^TLS required but neither TLS or STARTTLS"):
            _ = await transport.send(email())


async def test_an_implicit_tls_session_never_starts_tls_again(certificate: Certificate) -> None:
    async with ScriptedSmtpServer(
        tls_context=certificate.server_context(), implicit_tls=True
    ) as server:
        server.capabilities = ["STARTTLS"]
        transport = EsmtpTransport("localhost", server.port, True).set_verify_peer(False)

        _ = await transport.set_require_tls(True).send(email())

    assert "STARTTLS" not in server.commands
    assert len(server.messages) == 1


async def test_a_certificate_that_cannot_be_verified_is_refused(certificate: Certificate) -> None:
    async with _starttls_server(certificate) as server:
        transport = esmtp_transport(server, host="localhost")

        with pytest.raises(TransportError, match=r"^Unable to connect with STARTTLS: "):
            _ = await transport.send(email())

    assert not any(command.startswith("MAIL") for command in server.commands)


def test_the_peer_is_verified_by_default() -> None:
    assert EsmtpTransport().is_peer_verified()
    assert not EsmtpTransport().set_verify_peer(False).is_peer_verified()


def test_the_timeout_reads_back() -> None:
    assert EsmtpTransport().get_timeout() == 60.0
    assert EsmtpTransport().set_timeout(5).get_timeout() == 5.0
