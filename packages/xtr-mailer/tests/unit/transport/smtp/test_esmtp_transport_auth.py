"""Authentication on an ESMTP session: the authenticators tried in turn, and their failures."""

from __future__ import annotations

import pytest

from tests.support.scripted_smtp_server import STALL, ScriptedSmtpServer
from tests.support.smtp_sends import email, esmtp_transport
from xtr_mailer.exception import TransportError
from xtr_mailer.transport.smtp import EsmtpTransport
from xtr_mailer.transport.smtp.auth import (
    CramMd5Authenticator,
    LoginAuthenticator,
    PlainAuthenticator,
    XOAuth2Authenticator,
)

pytestmark = pytest.mark.anyio

_REFUSED = "535 5.7.139 Authentication unsuccessful"
_CHALLENGE = "334 PDAxMjM0NTY3ODkuMDEyMzQ1NjdAZXhhbXBsZS5vcmc+"
_CRAM_MD5 = ["AUTH CRAM-MD5", "dGVzdHVzZXIgMzU5OGQ3NWFiMzFlOWIxNGQyODI0ODE1MjExMGUyZDA="]
_PLAIN = ["AUTH PLAIN dGVzdHVzZXIAdGVzdHVzZXIAcDRzc3cwcmQ="]
_LOGIN = ["AUTH LOGIN", "dGVzdHVzZXI=", "cDRzc3cwcmQ="]
_XOAUTH2 = ["AUTH XOAUTH2 dXNlcj10ZXN0dXNlcgFhdXRoPUJlYXJlciBwNHNzdzByZAEB"]


def _server_offering_every_mechanism() -> ScriptedSmtpServer:
    server = ScriptedSmtpServer()
    server.capabilities = ["AUTH PLAIN LOGIN CRAM-MD5 XOAUTH2"]
    return server


def _transport(server: ScriptedSmtpServer) -> EsmtpTransport:
    return esmtp_transport(server).set_username("testuser").set_password("p4ssw0rd")


async def _failed_send(transport: EsmtpTransport) -> TransportError:
    with pytest.raises(TransportError) as caught:
        _ = await transport.send(email())
    return caught.value


async def test_the_default_authenticators_are_tried_in_turn() -> None:
    async with _server_offering_every_mechanism() as server:
        server.replies["AUTH"] = [_CHALLENGE, _REFUSED, _REFUSED, "334 VXNlcm5hbWU6"]
        server.replies["AUTH"] += ["334 UGFzc3dvcmQ6", _REFUSED, _REFUSED]

        error = await _failed_send(_transport(server))

    assert str(error).startswith(
        "Failed to authenticate on SMTP server using the following authenticators: "
        '"CRAM-MD5", "PLAIN", "LOGIN", "XOAUTH2". Authenticator "CRAM-MD5" returned '
        '"Expected response code "235" but got code "535", with message '
        f'"{_REFUSED}".".'
    )
    assert error.code == 535
    assert server.commands == [
        "EHLO [127.0.0.1]",
        *_CRAM_MD5,
        "RSET",
        *_PLAIN,
        "RSET",
        *_LOGIN,
        "RSET",
        *_XOAUTH2,
        "RSET",
    ]


async def test_the_authenticators_given_are_the_ones_tried() -> None:
    async with _server_offering_every_mechanism() as server:
        server.replies["AUTH"] = [_CHALLENGE, _REFUSED, "334 VXNlcm5hbWU6", "334 UGFzc3dvcmQ6"]
        server.replies["AUTH"] += [_REFUSED]
        transport = EsmtpTransport(
            server.host,
            server.port,
            authenticators=[CramMd5Authenticator(), LoginAuthenticator()],
        ).set_timeout(2.0)

        error = await _failed_send(transport.set_username("testuser").set_password("p4ssw0rd"))

    assert str(error).startswith(
        "Failed to authenticate on SMTP server using the following authenticators: "
        '"CRAM-MD5", "LOGIN".'
    )
    assert server.commands == ["EHLO [127.0.0.1]", *_CRAM_MD5, "RSET", *_LOGIN, "RSET"]


async def test_set_authenticators_replaces_them() -> None:
    async with _server_offering_every_mechanism() as server:
        server.replies["AUTH"] = [_REFUSED]
        transport = _transport(server)
        transport.set_authenticators([XOAuth2Authenticator()])

        error = await _failed_send(transport)

    assert str(error).startswith(
        'Failed to authenticate on SMTP server using the following authenticators: "XOAUTH2".'
    )
    assert server.commands == ["EHLO [127.0.0.1]", *_XOAUTH2, "RSET"]


async def test_no_authenticator_for_the_offered_mechanisms_is_refused() -> None:
    async with _server_offering_every_mechanism() as server:
        transport = _transport(server)
        transport.set_authenticators([])

        error = await _failed_send(transport)

    assert str(error) == (
        "Failed to find an authenticator supported by the SMTP server, which currently "
        'supports: "plain", "login", "cram-md5", "xoauth2".'
    )
    assert error.code == 504


async def test_a_lost_connection_during_authentication_is_raised_as_it_is() -> None:
    async with _server_offering_every_mechanism() as server:
        server.replies["AUTH"] = ["334 VXNlcm5hbWU6", "334 UGFzc3dvcmQ6", STALL]
        transport = _transport(server).set_timeout(0.2)
        transport.set_authenticators([LoginAuthenticator()])

        error = await _failed_send(transport)

    assert str(error) == f'Connection to "127.0.0.1:{server.port}" timed out.'
    assert server.commands == ["EHLO [127.0.0.1]", *_LOGIN]


async def test_the_next_authenticator_may_succeed() -> None:
    async with _server_offering_every_mechanism() as server:
        server.replies["AUTH"] = [_CHALLENGE, _REFUSED, "235 2.7.0 Accepted"]

        _ = await _transport(server).send(email())

    assert server.commands[:5] == ["EHLO [127.0.0.1]", *_CRAM_MD5, "RSET", *_PLAIN]
    assert len(server.messages) == 1


async def test_no_username_skips_authentication() -> None:
    async with _server_offering_every_mechanism() as server:
        _ = await esmtp_transport(server).send(email())

    assert not any(command.startswith("AUTH") for command in server.commands)


async def test_a_server_offering_no_authentication_is_not_asked_for_it() -> None:
    async with ScriptedSmtpServer() as server:
        _ = await _transport(server).send(email())

    assert not any(command.startswith("AUTH") for command in server.commands)


def test_add_authenticator_appends_one() -> None:
    transport = EsmtpTransport(authenticators=[])

    transport.add_authenticator(PlainAuthenticator())

    assert [each.get_auth_keyword() for each in transport._authenticators] == ["PLAIN"]
