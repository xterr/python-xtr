from __future__ import annotations

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from xtr_mailer.exception import InvalidArgumentError
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
