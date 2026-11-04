"""SMTP transports inside round-robin and failover groups: stopped together, reopened alone."""

from __future__ import annotations

import pytest

from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_sends import envelope, raw, smtp_transport
from xtr_mailer.transport import FailoverTransport, NullTransport, RoundRobinTransport

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("first_turn")]


async def test_stop_closes_every_smtp_session_and_a_later_send_reopens_them() -> None:
    async with ScriptedSmtpServer() as first, ScriptedSmtpServer() as nested:
        smtp = smtp_transport(first)
        nested_smtp = smtp_transport(nested)
        transport = RoundRobinTransport([smtp, FailoverTransport([nested_smtp]), NullTransport()])
        for _ in range(3):
            _ = await transport.send(raw(), envelope())
        open_before = (smtp._client.is_connected, nested_smtp._client.is_connected)

        await transport.stop()
        open_after_stop = (smtp._client.is_connected, nested_smtp._client.is_connected)
        for _ in range(3):
            _ = await transport.send(raw(), envelope())
        open_again = (smtp._client.is_connected, nested_smtp._client.is_connected)
        quits = (first.commands.count("QUIT"), nested.commands.count("QUIT"))
        await transport.stop()

    assert open_before == (True, True)
    assert open_after_stop == (False, False)
    assert open_again == (True, True)
    assert (len(first.peers), len(nested.peers)) == (2, 2)
    assert quits == (1, 1)
