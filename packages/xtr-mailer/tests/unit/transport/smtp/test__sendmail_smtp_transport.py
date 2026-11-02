from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_mime import Address, RawMessage

from tests.support.sendmail_fakes import FakeSendmail, assert_reaped, fake_command
from xtr_mailer import Envelope
from xtr_mailer.transport.smtp import SmtpTransport
from xtr_mailer.transport.smtp._sendmail_smtp_transport import SendmailSmtpTransport

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


def _envelope() -> Envelope:
    return Envelope(Address("from@mail.com"), [Address("to@mail.com")])


def test_it_is_an_smtp_transport_named_after_sendmail() -> None:
    transport = SendmailSmtpTransport(fake_command("-bs"))

    assert isinstance(transport, SmtpTransport)
    assert str(transport) == "smtp://sendmail"


def test_its_timeout_bounds_the_wait_for_the_child_too() -> None:
    transport = SendmailSmtpTransport(fake_command("-bs")).set_timeout(3)

    assert transport.get_timeout() == 3
    assert transport._channel._timeout == 3


async def test_each_session_runs_a_child_of_its_own(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    transport = SendmailSmtpTransport(fake_command("-bs")).set_restart_threshold(1)

    _ = await transport.send(RawMessage(b"one"), _envelope())
    first = fake.pid
    _ = await transport.send(RawMessage(b"two"), _envelope())
    second = fake.pid
    await transport.stop()

    assert first != second
    await assert_reaped(first)
    await assert_reaped(second)
    assert fake.messages.read_bytes() == b"one\r\ntwo\r\n"
