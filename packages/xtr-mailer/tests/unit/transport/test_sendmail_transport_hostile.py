"""A hostile sendmail gets nothing but the package's errors, within the timeout, and no zombie."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from xtr_mime import Address, RawMessage

from tests.support.sendmail_fakes import FakeSendmail, assert_reaped, fake_command
from xtr_mailer import Envelope, MailerError, TransportError
from xtr_mailer.transport import SendmailTransport

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_TIMEOUT = 0.5
#: Far beyond the transport's timeout: a test failing here waited forever.
_GIVE_UP = 10.0
_MEGABYTES = 5 * 1024 * 1024


def _envelope() -> Envelope:
    return Envelope(Address("from@mail.com"), [Address("recipient@mail.com")])


async def _refusal(transport: SendmailTransport, message: bytes = b"x") -> MailerError:
    with pytest.raises(MailerError) as caught:
        async with asyncio.timeout(_GIVE_UP):
            _ = await transport.send(RawMessage(message), _envelope())
    async with asyncio.timeout(_GIVE_UP):
        await transport.stop()
    return caught.value


def _piping(flags: tuple[str, ...] = ("-t",)) -> SendmailTransport:
    return SendmailTransport(fake_command(*flags)).set_timeout(_TIMEOUT)


async def test_a_hanging_sendmail_is_killed_at_the_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, hang="1")

    error = await _refusal(_piping())

    assert type(error) is TransportError
    assert str(error) == "Process did not finish within 0.5 seconds."
    await assert_reaped(fake.pid)


async def test_megabytes_of_errors_are_cut_short_in_the_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, exit="1", stderr=str(10 * 1024 * 1024))

    error = await _refusal(_piping())

    assert str(error).startswith("Process failed with exit code 1: eeee")
    assert str(error).endswith("…")
    assert len(str(error)) < 1100
    await assert_reaped(fake.pid)


async def test_what_sendmail_writes_is_shown_escaped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path, exit="1", output="bad\r\nBcc: x\x1b[31m\n")

    error = await _refusal(_piping())

    assert str(error) == "Process failed with exit code 1: bad\\r\\nBcc: x\\x1b[31m"


async def test_a_sendmail_exiting_mid_message_fails_with_its_status(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, read="1000", exit="3")

    error = await _refusal(_piping(), b"x" * _MEGABYTES)

    assert str(error) == "Process failed with exit code 3: "
    await assert_reaped(fake.pid)


async def test_a_sendmail_closing_its_input_early_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, read="10", close_input="1")

    # It waits half a second before exiting: the timeout must outlast that.
    error = await _refusal(_piping().set_timeout(5), b"x" * _MEGABYTES)

    assert str(error) == "Process closed its input before the whole message was written."
    await assert_reaped(fake.pid)


async def test_a_sendmail_that_cannot_start_fails(tmp_path: Path) -> None:
    transport = SendmailTransport(f"{tmp_path / 'missing'} -t")

    error = await _refusal(transport)

    assert type(error) is TransportError
    assert str(error).startswith("Process could not be started: ")


@pytest.mark.parametrize("flag", ["-t", "-bs"])
async def test_a_cancelled_send_kills_and_reaps_sendmail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag: str
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, hang="1")
    transport = SendmailTransport(fake_command(flag))
    sending = asyncio.ensure_future(transport.send(RawMessage(b"x"), _envelope()))
    pid = await fake.started()

    _ = sending.cancel()
    with pytest.raises(asyncio.CancelledError):
        await sending

    await assert_reaped(pid)
    await transport.stop()


async def test_a_silent_interactive_sendmail_fails_within_the_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, hang="1")

    error = await _refusal(_piping(("-bs",)))

    assert isinstance(error, TransportError)
    await assert_reaped(fake.pid)


async def test_an_interactive_sendmail_speaking_garbage_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, garbage="1")

    error = await _refusal(_piping(("-bs",)))

    assert isinstance(error, TransportError)
    await assert_reaped(fake.pid)


async def test_an_interactive_sendmail_dying_mid_session_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, die_at="RCPT")

    error = await _refusal(_piping(("-bs",)))

    assert isinstance(error, TransportError)
    await assert_reaped(fake.pid)


async def test_an_interactive_sendmail_flooding_its_errors_still_delivers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, stderr=str(10 * 1024 * 1024))
    transport = _piping(("-bs",))

    sent = await transport.send(RawMessage(b"x"), _envelope())
    await transport.stop()

    assert sent is not None
    await assert_reaped(fake.pid)


async def test_stop_never_raises_when_sendmail_dies_at_quit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, die_at="QUIT")
    transport = _piping(("-bs",))
    _ = await transport.send(RawMessage(b"x"), _envelope())

    await transport.stop()

    await assert_reaped(fake.pid)


async def test_stop_kills_an_interactive_sendmail_that_outlives_its_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, linger="1")
    transport = _piping(("-bs",))
    _ = await transport.send(RawMessage(b"x"), _envelope())

    async with asyncio.timeout(_GIVE_UP):
        await transport.stop()

    await assert_reaped(fake.pid)


async def test_a_stop_cancelled_while_waiting_for_sendmail_kills_and_reaps_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, linger="1")
    transport = SendmailTransport(fake_command("-bs"))  # Waits a minute for it to exit.
    _ = await transport.send(RawMessage(b"x"), _envelope())

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.3):
            await transport.stop()

    await assert_reaped(fake.pid)
