"""A hostile server gets nothing but the package's errors, within the timeout, and no secret."""

from __future__ import annotations

import asyncio
import base64
import time
from typing import TYPE_CHECKING, NoReturn

import pytest

from tests.support.recording_logger import RecordingLogger
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_sends import email, esmtp_transport
from xtr_mailer.exception import (
    InvalidArgumentError,
    MailerError,
    TransportError,
    UnexpectedResponseError,
)
from xtr_mailer.transport import FailoverTransport, Transport
from xtr_mailer.transport.smtp.auth import (
    CramMd5Authenticator,
    LoginAuthenticator,
    PlainAuthenticator,
    XOAuth2Authenticator,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from xtr_mailer.transport.smtp import EsmtpTransport
    from xtr_mailer.transport.smtp.auth import AuthenticatorInterface

pytestmark = pytest.mark.anyio

_USER = "s3cret-user"
_PASSWORD = "s3cret-pass"
_PLAIN = base64.b64encode(f"{_USER}\0{_USER}\0{_PASSWORD}".encode()).decode()
_SECRETS = (_USER, _PASSWORD, _PLAIN, base64.b64encode(_PASSWORD.encode()).decode())


def _chain(error: BaseException) -> Iterator[BaseException]:
    current: BaseException | None = error
    while current is not None:
        yield current
        current = current.__cause__ or current.__context__


def _assert_shows_no_secret(error: BaseException) -> None:
    assert error.__context__ is None
    for link in _chain(error):
        for secret in _SECRETS:
            assert secret not in str(link)
            assert secret not in repr(link)
            assert secret not in repr(link.args)
            assert secret not in getattr(link, "debug", "")


class _RawPasswordAuthenticator:
    """Writes the password as it is, whatever characters it holds."""

    def get_auth_keyword(self) -> str:
        return "PLAIN"

    async def authenticate(self, client: EsmtpTransport) -> None:
        _ = await client.execute_command(f"AUTH PLAIN {client.get_password()}", [235])


async def _refusal(server: ScriptedSmtpServer, *, reply_timeout: float = 2.0) -> MailerError:
    return await _refusal_of(esmtp_transport(server).set_timeout(reply_timeout))


async def _refusal_of(transport: EsmtpTransport) -> MailerError:
    with pytest.raises(MailerError) as caught:
        _ = await transport.send(email())
    await transport.stop()
    return caught.value


@pytest.mark.parametrize(
    "reply",
    [
        "garbage",
        "\udcff\udcfe\x00\x1b[31m",
        "250-fine\r\nnot a reply line",
        "250-fine\r\n550 5.7.1 but no",
        "250 " + "x" * 9000,
        "550-" + "\r\n550-".join(["y" * 900] * 200) + "\r\n550 end",
    ],
)
async def test_a_hostile_reply_to_mail_from_is_an_unexpected_response(reply: str) -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["MAIL"] = [reply]

        error = await _refusal(server)

    assert isinstance(error, UnexpectedResponseError)
    _ = str(error).encode()
    _ = error.debug.encode()
    assert len(str(error)) < 2_000_000


@pytest.mark.parametrize("greeting", ["garbage", "\udcff\udcfe", "220-a\r\n554 b"])
async def test_a_hostile_greeting_is_a_transport_error(greeting: str) -> None:
    async with ScriptedSmtpServer() as server:
        server.greeting = greeting

        error = await _refusal(server)

    assert isinstance(error, TransportError)
    _ = str(error).encode()


async def test_a_hostile_capability_list_is_read_without_failing() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["\udcffBAD", "AUTH", "SIZE=" + "9" * 4000, "-", "AUTH  "]
        transport = esmtp_transport(server)

        _ = await transport.send(email())
        await transport.stop()

    assert len(server.messages) == 1


async def test_a_hostile_message_id_is_read_without_failing() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["DATA_END"] = ["250 Ok: queued as " + "A" * 8000]
        transport = esmtp_transport(server)

        sent = await transport.send(email())
        await transport.stop()

    assert sent is not None
    assert sent.get_message_id() == "A" * 8000


@pytest.mark.parametrize("verb", ["MAIL", "RCPT", "DATA", "DATA_END", "EHLO", "HELO"])
async def test_a_silent_server_fails_within_the_timeout(verb: str) -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add(verb)
        if verb == "HELO":
            server.replies["EHLO"] = ["502 no"]
        started = time.monotonic()

        error = await _refusal(server, reply_timeout=0.2)
        elapsed = time.monotonic() - started

    assert isinstance(error, TransportError)
    assert elapsed < 2.0


async def test_a_server_echoing_the_credentials_never_shows_them() -> None:
    logger = RecordingLogger()
    echo = f"535 5.7.8 Rejected {_USER} {_PASSWORD} {_PLAIN}"
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["AUTH PLAIN LOGIN"]
        server.replies["AUTH"] = [echo, f"334 {_USER}", f"334 {_PASSWORD}", echo]
        server.replies["RSET"] = [echo, echo]
        transport = esmtp_transport(server, logger=logger).set_username(_USER)
        transport = transport.set_password(_PASSWORD)

        with pytest.raises(TransportError) as caught:
            _ = await transport.send(email())
        await transport.stop()

    assert "[redacted]" in str(caught.value)
    for error in _chain(caught.value):
        for secret in _SECRETS:
            assert secret not in str(error)
            assert secret not in repr(error)
            assert secret not in getattr(error, "debug", "")
    for line in logger.records:
        assert all(secret not in line for secret in _SECRETS)


async def test_a_server_echoing_the_credentials_into_the_debug_log_never_shows_them() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["AUTH PLAIN"]
        server.replies["AUTH"] = [f"235 2.7.0 Welcome {_USER}, {_PASSWORD}, {_PLAIN}"]
        transport = esmtp_transport(server).set_username(_USER).set_password(_PASSWORD)

        sent = await transport.send(email())
        await transport.stop()

    assert sent is not None
    assert "AUTH PLAIN [redacted]" in sent.get_debug()
    assert all(secret not in sent.get_debug() for secret in _SECRETS)


async def test_a_command_that_cannot_be_encoded_is_an_invalid_argument() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["AUTH PLAIN"]
        transport = esmtp_transport(server).set_username("user").set_password("\udcff")
        transport.set_authenticators([_RawPasswordAuthenticator()])

        error = await _refusal_of(transport)

    assert isinstance(error, InvalidArgumentError)
    assert "\udcff" not in str(error)


async def test_a_malformed_reply_echoing_the_credentials_leaves_them_out_of_the_context() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["AUTH PLAIN"]
        server.replies["MAIL"] = [f"XX5 echo {_PLAIN} {_PASSWORD}"]
        transport = esmtp_transport(server).set_username(_USER).set_password(_PASSWORD)

        error = await _refusal_of(transport)

    assert isinstance(error, UnexpectedResponseError)
    _assert_shows_no_secret(error)


async def test_a_malformed_end_of_data_reply_leaves_the_password_out_of_the_context() -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = ["AUTH PLAIN"]
        server.replies["DATA_END"] = [f"QQQ {_PASSWORD}"]
        transport = esmtp_transport(server).set_username(_USER).set_password(_PASSWORD)

        error = await _refusal_of(transport)

    assert isinstance(error, UnexpectedResponseError)
    _assert_shows_no_secret(error)


@pytest.mark.parametrize(
    ("authenticator", "replies"),
    [
        (CramMd5Authenticator(), []),
        (PlainAuthenticator(), []),
        (LoginAuthenticator(), ["334 VXNlcm5hbWU6", "334 UGFzc3dvcmQ6"]),
        (XOAuth2Authenticator(), []),
    ],
)
async def test_a_password_utf8_cannot_write_is_left_out_of_the_context(
    authenticator: AuthenticatorInterface, replies: list[str]
) -> None:
    async with ScriptedSmtpServer() as server:
        server.capabilities = [f"AUTH {authenticator.get_auth_keyword()}"]
        server.replies["AUTH"] = list(replies)
        transport = esmtp_transport(server).set_username(_USER)
        transport = transport.set_password(_PASSWORD + "\udcff")
        transport.set_authenticators([authenticator])

        error = await _refusal_of(transport)

    assert isinstance(error, InvalidArgumentError)
    _assert_shows_no_secret(error)


async def test_a_resolver_refusing_the_first_host_lets_failover_reach_the_backup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def refuse(*arguments: object, **options: object) -> NoReturn:
        del arguments, options
        raise UnicodeError("encoding with 'idna' codec failed")

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", refuse)
    async with ScriptedSmtpServer() as server:
        transport = Transport.from_dsn(
            f"failover(smtp://mail.example.com:2525?auto_tls=0 "
            f"smtp://{server.host}:{server.port}?auto_tls=0)"
        )
        assert isinstance(transport, FailoverTransport)

        sent = await transport.send(email())
        await transport.stop()

    assert sent is not None
    assert len(server.messages) == 1
