from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from xtr_mime import Address, Email, RawMessage

from tests.support.recorded_events import recording_dispatcher
from tests.support.sendmail_fakes import (
    FAKE_SENDMAIL,
    FakeSendmail,
    assert_reaped,
    fake_command,
)
from xtr_mailer import Envelope, InvalidArgumentError, TransportError
from xtr_mailer.event import MessageEvent, SentMessageEvent
from xtr_mailer.transport import SendmailTransport, StoppableTransportInterface

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio


def _mail() -> Email:
    return Email().from_("from@mail.com").to("to@mail.com").subject("Subject").text("Some text")


def _mail_and_envelope() -> tuple[Email, Envelope]:
    mail = _mail()
    envelope = Envelope.create(mail)
    envelope.set_recipients([Address("recipient@mail.com")])
    return mail, envelope


def _envelope() -> Envelope:
    return Envelope(Address("from@mail.com"), [Address("recipient@mail.com")])


def test_it_is_named_after_sendmail() -> None:
    assert str(SendmailTransport()) == "smtp://sendmail"
    assert str(SendmailTransport("/usr/sbin/sendmail -t")) == "smtp://sendmail"


def test_it_is_a_stoppable_transport() -> None:
    assert isinstance(SendmailTransport(), StoppableTransportInterface)


async def test_the_message_recipients_are_used_when_the_envelope_names_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    mail = _mail()

    _ = await SendmailTransport(fake_command("-t")).send(mail, Envelope.create(mail))

    assert fake.argv == [str(FAKE_SENDMAIL), "-i", "-ffrom@mail.com", "--", "to@mail.com"]


async def test_the_envelope_recipients_are_used_when_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)

    _ = await SendmailTransport(fake_command("-t")).send(*_mail_and_envelope())

    assert fake.argv == [str(FAKE_SENDMAIL), "-i", "-ffrom@mail.com", "--", "recipient@mail.com"]


async def test_a_failing_sendmail_raises_a_transport_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path, exit="42", output="Sending failed")

    with pytest.raises(TransportError) as caught:
        _ = await SendmailTransport(fake_command("-t")).send(*_mail_and_envelope())

    assert str(caught.value) == "Process failed with exit code 42: Sending failed"


async def test_a_failed_sendmail_is_reaped_and_the_next_send_starts_afresh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, exit="42")
    transport = SendmailTransport(fake_command("-t"))
    with pytest.raises(TransportError):
        _ = await transport.send(*_mail_and_envelope())
    failed = fake.pid
    monkeypatch.setenv("FAKE_SENDMAIL_EXIT", "0")

    sent = await transport.send(*_mail_and_envelope())

    await assert_reaped(failed)
    assert sent is not None
    assert fake.pid != failed


async def test_an_interactive_sendmail_exiting_with_a_failure_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path, exit="42")
    transport = SendmailTransport(fake_command("-bs"))

    sent = await transport.send(*_mail_and_envelope())
    await transport.stop()

    assert sent is not None
    assert fake.argv == [str(FAKE_SENDMAIL), "-bs"]


async def test_an_interactive_sendmail_delivers_over_smtp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    transport = SendmailTransport(fake_command("-bs"))

    sent = await transport.send(RawMessage(b"Subject: x\r\n\r\n.dot\r\n"), _envelope())
    await transport.stop()

    assert sent is not None
    assert sent.get_message_id() == "FAKE42"
    assert "> RCPT TO:<recipient@mail.com>" in sent.get_debug()
    assert fake.messages.read_bytes() == b"Subject: x\r\n\r\n.dot\r\n"


async def test_stop_stops_the_interactive_transport(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    transport = SendmailTransport(fake_command("-bs"))
    _ = await transport.send(*_mail_and_envelope())
    first = fake.pid
    os.kill(first, 0)  # The session, and so the child, is still open.

    await transport.stop()
    await assert_reaped(first)
    _ = await transport.send(*_mail_and_envelope())

    second = fake.pid
    assert second != first
    os.kill(second, 0)
    await transport.stop()
    await assert_reaped(second)


async def test_stopping_a_transport_that_never_sent_does_nothing() -> None:
    await SendmailTransport().stop()
    await SendmailTransport("/usr/sbin/sendmail -t").stop()


@pytest.mark.parametrize(
    ("flags", "kept"),
    [
        pytest.param(("-t",), ["-i"], id="-i added"),
        pytest.param(("-t", "-i"), ["-i"], id="-i"),
        pytest.param(("-oi", "-t"), ["-oi"], id="-oi"),
    ],
)
async def test_the_message_is_piped_with_lf_line_endings_and_its_dots_as_written(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flags: tuple[str, ...], kept: list[str]
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)

    _ = await SendmailTransport(fake_command(*flags)).send(
        RawMessage(b"Subject: x\r\n\r\n.dot\r\n.\r\nend\r\n"), _envelope()
    )

    assert fake.input == b"Subject: x\n\n.dot\n.\nend\n"
    assert [flag for flag in fake.argv if flag in {"-i", "-oi"}] == kept


async def test_a_sender_the_command_names_is_kept(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)

    _ = await SendmailTransport(fake_command("-t", "-fbounce@example.com")).send(
        RawMessage(b"x"), _envelope()
    )

    assert fake.argv == [
        str(FAKE_SENDMAIL),
        "-fbounce@example.com",
        "-i",
        "--",
        "recipient@mail.com",
    ]


async def test_a_sender_sendmail_could_read_as_an_option_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    envelope = Envelope(Address("-oQ/tmp@example.com"), [Address("recipient@mail.com")])

    with pytest.raises(InvalidArgumentError) as caught:
        _ = await SendmailTransport(fake_command("-t")).send(RawMessage(b"x"), envelope)

    assert str(caught.value) == (
        'The envelope sender "-oQ/tmp@example.com" cannot be handed to sendmail: it starts '
        "with a hyphen, which sendmail could read as an option."
    )
    assert not fake.record.exists()


async def test_a_recipient_starting_with_a_hyphen_follows_the_end_of_the_options(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    envelope = Envelope(Address("from@mail.com"), [Address("-oQ@example.com")])

    _ = await SendmailTransport(fake_command("-t")).send(RawMessage(b"x"), envelope)

    assert fake.argv[-2:] == ["--", "-oQ@example.com"]


async def test_the_command_is_never_run_through_a_shell(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = FakeSendmail(monkeypatch, tmp_path)
    marker = tmp_path / "pwned"
    hostile = f"$(touch {marker}); touch {marker}"

    _ = await SendmailTransport(fake_command("-t", hostile)).send(RawMessage(b"x"), _envelope())

    assert fake.argv[1] == hostile
    assert not marker.exists()


@pytest.mark.parametrize(
    "command",
    ["/usr/sbin/sendmail", "/usr/sbin/sendmail -oi", "/usr/sbin/sendmail -bsx", "-t", ""],
)
def test_a_command_without_bs_or_t_is_refused(command: str) -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SendmailTransport(command)

    assert str(caught.value) == (
        f'Unsupported sendmail command flags "{command}"; must be one of "-bs" or "-t" but can '
        "include additional flags."
    )


def test_a_command_with_a_control_character_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SendmailTransport("/usr/sbin/sendmail\x00 -t")

    assert str(caught.value) == "The sendmail command must not contain control characters."


def test_a_command_whose_quotes_do_not_close_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as caught:
        _ = SendmailTransport('/usr/sbin/sendmail -t "-fa@example.com')

    assert str(caught.value) == (
        'The sendmail command "/usr/sbin/sendmail -t "-fa@example.com" does not parse: '
        "a quote or an escape is not closed."
    )


@pytest.mark.parametrize("seconds", [0, -1, float("inf"), float("nan")])
def test_a_timeout_that_is_not_a_positive_number_is_refused(seconds: float) -> None:
    with pytest.raises(InvalidArgumentError, match="timeout must be a positive number"):
        _ = SendmailTransport("/usr/sbin/sendmail -t").set_timeout(seconds)


def test_the_timeout_is_kept() -> None:
    assert SendmailTransport().set_timeout(2.5).get_timeout() == 2.5
    assert SendmailTransport("/usr/sbin/sendmail -t").get_timeout() == 60.0


@pytest.mark.parametrize("flag", ["-t", "-bs"])
async def test_the_email_is_announced_as_sent_through_sendmail(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, flag: str
) -> None:
    _ = FakeSendmail(monkeypatch, tmp_path)
    dispatcher, recorded = recording_dispatcher()
    transport = SendmailTransport(fake_command(flag), event_dispatcher=dispatcher)

    _ = await transport.send(*_mail_and_envelope())
    await transport.stop()

    assert [type(event) for event in recorded] == [MessageEvent, SentMessageEvent]
    first = recorded[0]
    assert isinstance(first, MessageEvent)
    assert first.get_transport() == "smtp://sendmail"
