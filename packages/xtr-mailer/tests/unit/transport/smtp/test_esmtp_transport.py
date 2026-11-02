from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typing_extensions import override
from xtr_mime import Email

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_sends import email, esmtp_transport
from xtr_mailer.exception import InvalidArgumentError, TransportError, UnexpectedResponseError
from xtr_mailer.transport.smtp import EsmtpTransport, SmtpTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

pytestmark = pytest.mark.anyio


class _DsnEsmtpTransport(EsmtpTransport):
    """Asks for delivery status notifications when the server offers them."""

    @override
    async def execute_command(self, command: str, codes: Sequence[int]) -> str:
        if "DSN" in self._get_capabilities():
            if command.startswith("MAIL FROM:"):
                command += " RET=HDRS"
            elif command.startswith("RCPT TO:"):
                command += " NOTIFY=FAILURE"
        return await super().execute_command(command, codes)


def _unicode_email(sender: str, recipient: str) -> Email:
    return Email().from_(sender).add_to(recipient).text(".")


@pytest.mark.parametrize(
    ("transport", "name"),
    [
        (EsmtpTransport(), "smtp://localhost"),
        (EsmtpTransport("example.com"), "smtps://example.com"),
        (EsmtpTransport("example.com", 2525), "smtp://example.com:2525"),
        (EsmtpTransport("example.com", 0, True), "smtps://example.com"),
        (EsmtpTransport("example.com", 0, False), "smtp://example.com"),
        (EsmtpTransport("example.com", 466, True), "smtps://example.com:466"),
        (EsmtpTransport("example.com", 465), "smtps://example.com"),
    ],
)
def test_its_name_is_its_scheme_host_and_any_port_off_the_default(
    transport: EsmtpTransport, name: str
) -> None:
    assert str(transport) == name


def test_it_is_an_smtp_transport() -> None:
    assert isinstance(EsmtpTransport(), SmtpTransport)


async def test_it_greets_with_ehlo() -> None:
    async with ScriptedSmtpServer() as server:
        _ = await esmtp_transport(server).send(email())

    assert server.commands[:2] == ["EHLO [127.0.0.1]", "MAIL FROM:<sender@example.org>"]


async def test_a_subclass_extends_the_commands_from_the_capabilities() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["DSN"]
        transport = _DsnEsmtpTransport(server.host, server.port).set_timeout(2.0)

        _ = await transport.send(email())

    assert "MAIL FROM:<sender@example.org> RET=HDRS" in server.commands
    assert "RCPT TO:<recipient@example.org> NOTIFY=FAILURE" in server.commands


async def test_a_non_ascii_local_part_goes_out_with_smtputf8_when_offered() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["SMTPUTF8"]

        _ = await esmtp_transport(server).send(_unicode_email("info@dømi.fo", "dømi@dømi.fo"))

    assert "MAIL FROM:<info@xn--dmi-0na.fo> SMTPUTF8" in server.commands
    assert "RCPT TO:<dømi@xn--dmi-0na.fo>" in server.commands


async def test_a_non_ascii_local_part_needs_the_server_to_offer_smtputf8() -> None:
    async with ScriptedSmtpServer() as server:
        transport = esmtp_transport(server)

        with pytest.raises(
            InvalidArgumentError,
            match=(
                r"^The SMTP server does not support the SMTPUTF8 extension required to send to "
                r"addresses with non-ASCII characters in their local-part\.$"
            ),
        ):
            _ = await transport.send(_unicode_email("info@dømi.fo", "dømi@dømi.fo"))

    assert not any(command.startswith("MAIL") for command in server.commands)


async def test_a_non_ascii_domain_alone_is_encoded_without_smtputf8() -> None:
    async with ScriptedSmtpServer() as server:
        _ = await esmtp_transport(server).send(_unicode_email("info@dømi.fo", "a@example.com"))

    assert "MAIL FROM:<info@xn--dmi-0na.fo>" in server.commands
    assert "RCPT TO:<a@example.com>" in server.commands


async def test_tls_required_on_a_plain_session_is_refused() -> None:
    async with ScriptedSmtpServer() as server:
        transport = esmtp_transport(server).set_require_tls(True)

        with pytest.raises(
            TransportError, match=r"^TLS required but neither TLS or STARTTLS are in use\.$"
        ):
            _ = await transport.send(email())

    assert not any(command.startswith("MAIL") for command in server.commands)


async def test_a_refused_ehlo_falls_back_to_helo() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["EHLO"] = ["502 5.5.1 EHLO not implemented"]

        _ = await esmtp_transport(server).send(email())

    assert server.commands[:2] == ["EHLO [127.0.0.1]", "HELO [127.0.0.1]"]
    assert len(server.messages) == 1


async def test_a_refused_helo_after_a_refused_ehlo_is_raised() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["EHLO"] = ["502 5.5.1 EHLO not implemented"]
        server.replies["HELO"] = ["501 5.5.4 Go away"]

        with pytest.raises(UnexpectedResponseError) as caught:
            await esmtp_transport(server).start()

    assert caught.value.code == 501


async def test_an_ehlo_that_lost_the_connection_is_raised_over_the_helo() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("EHLO")
        transport = esmtp_transport(server).set_timeout(0.2)

        with pytest.raises(TransportError, match="timed out"):
            await transport.start()


def test_the_settings_read_back() -> None:
    transport = (
        EsmtpTransport()
        .set_username("user")
        .set_password("secret")
        .set_auto_tls(False)
        .set_require_tls(True)
    )

    assert transport.get_username() == "user"
    assert transport.get_password() == "secret"
    assert not transport.is_auto_tls()
    assert transport.is_tls_required()


def test_tls_is_automatic_and_optional_by_default() -> None:
    transport = EsmtpTransport()

    assert transport.is_auto_tls()
    assert not transport.is_tls_required()


def test_its_name_never_shows_the_credentials() -> None:
    transport = EsmtpTransport("example.com").set_username("user").set_password("s3cret")

    assert "s3cret" not in f"{transport} {transport!r}"
    assert "user" not in f"{transport} {transport!r}"
