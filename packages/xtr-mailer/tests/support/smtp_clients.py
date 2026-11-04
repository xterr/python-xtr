"""SMTP clients pointed at a scripted server, and the message exchange they drive."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_mailer.transport.smtp._smtp_client import SmtpClient
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig

if TYPE_CHECKING:
    from tests.support.scripted_smtp_server import ScriptedSmtpServer

__all__ = ["connected_client", "send_data", "smtp_client"]


def smtp_client(server: ScriptedSmtpServer, *, timeout: float = 2.0) -> SmtpClient:
    """A client to ``server``, naming itself ``client.example``; not connected yet."""
    return SmtpClient(
        SmtpConnectionConfig(
            server.host, server.port, timeout=timeout, local_hostname="client.example"
        )
    )


async def connected_client(server: ScriptedSmtpServer) -> SmtpClient:
    """A client to ``server``, greeted."""
    client = smtp_client(server)
    _ = await client.connect()
    return client


async def send_data(client: SmtpClient, message: bytes) -> str:
    """Send ``DATA`` then ``message``; return the server's acceptance."""
    _ = await client.execute("DATA", [354])
    return await client.message(message)
