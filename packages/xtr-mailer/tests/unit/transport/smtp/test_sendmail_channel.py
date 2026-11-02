from __future__ import annotations

import asyncio
import shlex
import socket
import sys
from pathlib import Path

import pytest

from tests.support.smtp_clients import send_data
from xtr_mailer.exception import InvalidArgumentError, LogicError, TransportError
from xtr_mailer.transport.smtp._sendmail_channel import SendmailChannel
from xtr_mailer.transport.smtp._smtp_client import SmtpClient
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig

pytestmark = pytest.mark.anyio

FAKE_SENDMAIL = Path(__file__).parents[3] / "fixtures" / "fake_sendmail.py"


def _command(*arguments: str) -> str:
    return shlex.join([sys.executable, str(FAKE_SENDMAIL), "-bs", *arguments])


async def _start(channel: SendmailChannel) -> SmtpClient:
    client = SmtpClient(SmtpConnectionConfig(local_hostname="client.example", timeout=5.0))
    _ = await client.connect_socket(await channel.open(), channel.description)
    return client


async def test_a_message_is_delivered_through_the_child(tmp_path: Path) -> None:
    record = tmp_path / "mail.eml"
    channel = SendmailChannel(_command("--record", str(record)))
    client = await _start(channel)

    _ = await client.ehlo()
    _ = await client.execute("MAIL FROM:<sender@example.com>", [250])
    _ = await client.execute("RCPT TO:<rcpt@example.com>", [250])
    reply = await send_data(client, b"Subject: hi\r\n\r\n.body\r\n")
    _ = await client.execute("QUIT", [221])
    client.close()
    exit_code = await channel.close()

    assert reply == "250 2.0.0 Ok: queued as FAKE42"
    assert record.read_bytes() == b"Subject: hi\r\n\r\n.body\r\n"
    assert exit_code == 0


async def test_every_message_of_a_session_is_delivered_through_the_child(tmp_path: Path) -> None:
    # The child answers from its own process the moment a message ends, so a client
    # that yields between its last write and arming the reply read loses the reply.
    record = tmp_path / "mail.eml"
    messages = [f"Subject: {index}\r\n".encode() for index in range(20)]
    channel = SendmailChannel(_command("--record", str(record)))
    client = await _start(channel)

    replies = [await send_data(client, message) for message in messages]
    _ = await client.execute("QUIT", [221])
    client.close()
    exit_code = await channel.close()

    assert replies == ["250 2.0.0 Ok: queued as FAKE42"] * 20
    assert record.read_bytes() == b"".join(messages)
    assert exit_code == 0


async def test_its_description_names_the_command() -> None:
    assert SendmailChannel("/usr/sbin/sendmail -bs").description == "process /usr/sbin/sendmail -bs"


async def test_a_child_that_dies_mid_session_raises_a_transport_error() -> None:
    command = _command("--die-at", "MAIL")
    channel = SendmailChannel(command)
    client = await _start(channel)
    _ = await client.ehlo()

    with pytest.raises(TransportError) as caught:
        _ = await client.execute("MAIL FROM:<sender@example.com>", [250])
    exit_code = await channel.close()

    assert str(caught.value) == f'Connection to "process {command}" has been closed unexpectedly.'
    assert exit_code == 3


async def test_a_child_that_does_not_exit_is_killed() -> None:
    channel = SendmailChannel(_command("--linger"), timeout=0.2)
    client = await _start(channel)

    _ = await client.execute("QUIT", [221])
    client.close()
    exit_code = await channel.close()

    assert exit_code is not None
    assert exit_code < 0


async def test_closing_the_channel_ends_a_session_left_open() -> None:
    channel = SendmailChannel(_command())
    client = await _start(channel)

    exit_code = await channel.close()
    client.close()

    assert exit_code == 0


async def test_a_command_that_cannot_start_raises_a_transport_error(tmp_path: Path) -> None:
    channel = SendmailChannel(f"{tmp_path / 'missing-sendmail'} -bs")

    with pytest.raises(TransportError, match=r"^Process could not be started: "):
        _ = await channel.open()


async def test_a_command_that_does_not_parse_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="sendmail command"):
        _ = SendmailChannel('/usr/sbin/sendmail "-bs')


async def test_an_empty_command_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="sendmail command"):
        _ = SendmailChannel("  ")


async def test_closing_a_channel_never_opened_does_nothing() -> None:
    assert await SendmailChannel(_command()).close() is None


async def test_an_open_channel_refuses_to_open_again() -> None:
    channel = SendmailChannel(_command())
    client = await _start(channel)

    with pytest.raises(LogicError, match=r"^The sendmail channel is already open\.$"):
        _ = await channel.open()
    client.close()
    exit_code = await channel.close()

    assert exit_code == 0


async def test_opening_twice_at_once_starts_one_child() -> None:
    channel = SendmailChannel(_command())

    outcomes = await asyncio.gather(channel.open(), channel.open(), return_exceptions=True)
    exit_code = await channel.close()

    assert [isinstance(outcome, socket.socket) for outcome in outcomes] == [True, False]
    assert isinstance(outcomes[1], LogicError)
    assert exit_code is not None  # the one child started was waited for


async def test_a_closed_channel_can_open_again() -> None:
    channel = SendmailChannel(_command())
    client = await _start(channel)
    client.close()
    _ = await channel.close()

    client = await _start(channel)
    client.close()

    assert await channel.close() == 0


async def test_it_needs_a_posix_system(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    channel = SendmailChannel(_command())

    with pytest.raises(TransportError, match="POSIX"):
        _ = await channel.open()
