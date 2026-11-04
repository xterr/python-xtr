from __future__ import annotations

import asyncio
import socket
import sys
from typing import TYPE_CHECKING, NoReturn

import pytest

from tests.support.sendmail_fakes import FakeSendmail, assert_reaped, fake_command
from tests.support.smtp_clients import send_data
from xtr_mailer.exception import InvalidArgumentError, LogicError, TransportError
from xtr_mailer.transport.smtp._sendmail_channel import SendmailChannel
from xtr_mailer.transport.smtp._smtp_client import SmtpClient
from xtr_mailer.transport.smtp._smtp_connection_config import SmtpConnectionConfig

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


def _command() -> str:
    return fake_command("-bs")


async def _start(channel: SendmailChannel) -> SmtpClient:
    client = SmtpClient(SmtpConnectionConfig(local_hostname="client.example", timeout=5.0))
    _ = await client.connect_socket(await channel.open(), channel.description)
    return client


async def test_a_message_is_delivered_through_the_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    channel = SendmailChannel(_command())
    client = await _start(channel)

    _ = await client.ehlo()
    _ = await client.execute("MAIL FROM:<sender@example.com>", [250])
    _ = await client.execute("RCPT TO:<rcpt@example.com>", [250])
    reply = await send_data(client, b"Subject: hi\r\n\r\n.body\r\n")
    _ = await client.execute("QUIT", [221])
    client.close()
    exit_code = await channel.close()

    assert reply == "250 2.0.0 Ok: queued as FAKE42"
    assert fake.messages.read_bytes() == b"Subject: hi\r\n\r\n.body\r\n"
    assert exit_code == 0


async def test_every_message_of_a_session_is_delivered_through_the_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The child answers from its own process the moment a message ends, so a client
    # that yields between its last write and arming the reply read loses the reply.
    fake = FakeSendmail(monkeypatch, tmp_path)
    messages = [f"Subject: {index}\r\n".encode() for index in range(20)]
    channel = SendmailChannel(_command())
    client = await _start(channel)

    replies = [await send_data(client, message) for message in messages]
    _ = await client.execute("QUIT", [221])
    client.close()
    exit_code = await channel.close()

    assert replies == ["250 2.0.0 Ok: queued as FAKE42"] * 20
    assert fake.messages.read_bytes() == b"".join(messages)
    assert exit_code == 0


async def test_its_description_names_the_command() -> None:
    assert SendmailChannel("/usr/sbin/sendmail -bs").description == "process /usr/sbin/sendmail -bs"


async def test_a_child_that_dies_mid_session_raises_a_transport_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path, die_at="MAIL")
    command = _command()
    channel = SendmailChannel(command)
    client = await _start(channel)
    _ = await client.ehlo()

    with pytest.raises(TransportError) as caught:
        _ = await client.execute("MAIL FROM:<sender@example.com>", [250])
    exit_code = await channel.close()

    assert str(caught.value) == f'Connection to "process {command}" has been closed unexpectedly.'
    assert exit_code == 3


async def test_a_child_that_does_not_exit_is_killed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path, linger="1")
    channel = SendmailChannel(_command(), timeout=0.2)
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


async def test_a_child_released_unclean_is_killed_and_reaped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, linger="1")
    channel = SendmailChannel(_command())
    client = await _start(channel)
    pid = await fake.started()

    client.close()
    channel.release(kill=True)

    await assert_reaped(pid)
    exit_code = await channel.close()
    assert exit_code is not None
    assert exit_code < 0


async def test_a_child_released_after_its_session_exits_on_its_own(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    channel = SendmailChannel(_command())
    client = await _start(channel)
    pid = await fake.started()

    _ = await client.execute("QUIT", [221])
    client.close()
    channel.release(kill=False)

    assert await channel.close() == 0
    await assert_reaped(pid)


async def test_opening_again_reaps_the_released_child(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, linger="1")
    channel = SendmailChannel(_command(), timeout=0.2)
    client = await _start(channel)
    first = await fake.started()
    _ = await client.execute("QUIT", [221])
    client.close()
    channel.release(kill=False)
    fake.record.unlink()

    client = await _start(channel)

    await assert_reaped(first)
    assert await fake.started() != first
    client.close()
    channel.release(kill=True)
    _ = await channel.close()


async def test_releasing_a_channel_never_opened_does_nothing() -> None:
    channel = SendmailChannel(_command())

    channel.release(kill=True)

    assert await channel.close() is None


async def test_a_cancel_while_the_child_starts_closes_both_sockets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    made: list[socket.socket] = []
    socketpair = socket.socketpair

    def recorded_socketpair() -> tuple[socket.socket, socket.socket]:
        pair = socketpair()
        made.extend(pair)
        return pair

    async def cancelled(*_arguments: object, **_settings: object) -> NoReturn:
        raise asyncio.CancelledError

    monkeypatch.setattr(socket, "socketpair", recorded_socketpair)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", cancelled)

    with pytest.raises(asyncio.CancelledError):
        _ = await SendmailChannel(_command()).open()

    assert [each.fileno() for each in made] == [-1, -1]


async def test_a_command_the_system_cannot_take_fails_without_showing_it() -> None:
    with pytest.raises(TransportError) as caught:
        _ = await SendmailChannel("/usr/sbin/sendmail\ud800 -bs").open()

    assert str(caught.value) == (
        "Process could not be started: an argument holds a character the system cannot take."
    )


async def test_the_child_writes_its_errors_nowhere(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capfd: pytest.CaptureFixture[str]
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path, stderr="100")
    channel = SendmailChannel(_command())
    client = await _start(channel)

    _ = await client.execute("QUIT", [221])
    client.close()
    _ = await channel.close()

    assert capfd.readouterr().err == ""
