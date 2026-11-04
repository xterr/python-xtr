from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.dummy_transport import DummyTransport
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.scripted_transport import ScriptedTransport
from tests.support.sendmail_fakes import FakeSendmail, assert_reaped, fake_command
from tests.support.smtp_sends import envelope, raw, smtp_transport
from xtr_mailer import TransportError
from xtr_mailer.transport import RoundRobinTransport, SendmailTransport, Transports

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


class _Connection(ScriptedTransport):
    stops: int = 0
    error: Exception | None = None

    async def stop(self) -> None:
        self.stops += 1
        if self.error is not None:
            raise self.error


async def test_close_stops_the_transports_that_hold_a_connection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    async with ScriptedSmtpServer() as server, ScriptedSmtpServer() as other:
        smtp = smtp_transport(server)
        round_robin_smtp = smtp_transport(other)
        sendmail = SendmailTransport(fake_command("-bs"))
        transports = Transports(
            {
                "smtp": smtp,
                "roundrobin": RoundRobinTransport([round_robin_smtp]),
                "sendmail": sendmail,
                "dummy": DummyTransport("localhost"),
            }
        )
        await smtp.start()
        await round_robin_smtp.start()
        _ = await sendmail.send(raw(), envelope())

        await transports.close()
        closed = (smtp._client.is_connected, round_robin_smtp._client.is_connected)
        await assert_reaped(fake.pid)
        _ = await transports.send(raw(), envelope())
        reopened = smtp._client.is_connected
        await transports.close()

    assert closed == (False, False)
    assert reopened
    assert server.commands.count("QUIT") == 2
    assert other.commands.count("QUIT") == 1


async def test_close_stops_every_transport_then_raises_the_first_error() -> None:
    first, second, third = _Connection("smtp://a"), _Connection("smtp://b"), _Connection("smtp://c")
    first.error, second.error = TransportError("a"), TransportError("b")
    transports = Transports({"a": first, "b": second, "c": third})

    with pytest.raises(TransportError) as caught:
        await transports.close()

    assert caught.value is first.error
    assert (first.stops, second.stops, third.stops) == (1, 1, 1)


async def test_close_leaves_transports_holding_no_connection_alone() -> None:
    await Transports({"dummy": DummyTransport("localhost")}).close()
