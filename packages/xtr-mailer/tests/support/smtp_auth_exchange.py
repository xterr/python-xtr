"""One authenticator's exchange with a scripted server offering its mechanism."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_sends import esmtp_transport

if TYPE_CHECKING:
    from xtr_mailer.transport.smtp.auth import AuthenticatorInterface

__all__ = ["authenticate"]


async def authenticate(
    authenticator: AuthenticatorInterface,
    replies: list[str],
    *,
    password: str = "p4ssw0rd",
) -> list[str]:
    """Log in as ``testuser`` with ``authenticator`` alone; return the lines the server read.

    The server offers the authenticator's mechanism and answers the exchange from
    ``replies``, then accepts it.
    """
    async with ScriptedSmtpServer() as server:
        server.capabilities = [f"AUTH {authenticator.get_auth_keyword()}"]
        server.replies["AUTH"] = [*replies, "235 2.7.0 Authentication successful"]
        transport = esmtp_transport(server).set_username("testuser").set_password(password)
        transport.set_authenticators([authenticator])
        await transport.start()
        await transport.stop()
    return server.commands[1:-1]
