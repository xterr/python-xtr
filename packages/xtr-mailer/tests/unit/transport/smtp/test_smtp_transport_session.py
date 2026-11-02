"""The session an SMTP transport keeps: stopping, restarting, sharing, cancelling."""

from __future__ import annotations

import anyio
import pytest
from xtr_clock import MockClock

from tests.support.recorded_events import recording_dispatcher
from tests.support.recording_logger import RecordingLogger
from tests.support.scripted_smtp_server import ScriptedSmtpServer
from tests.support.smtp_sends import envelope, raw, smtp_transport
from xtr_mailer.event import MessageEvent, SentMessageEvent

pytestmark = pytest.mark.anyio


async def test_stop_quits_and_closes_the_connection() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server)
        _ = await transport.send(raw(), envelope())
        connected_before = transport._client.is_connected

        await transport.stop()

    assert connected_before
    assert not transport._client.is_connected
    assert server.commands[-1] == "QUIT"


async def test_stop_without_a_session_says_nothing() -> None:
    async with ScriptedSmtpServer() as server:
        await smtp_transport(server).stop()

    assert server.peers == []


async def test_a_send_after_stop_opens_a_new_session() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server)
        _ = await transport.send(raw("Message 1"), envelope())
        await transport.stop()

        _ = await transport.send(raw("Message 2"), envelope())

    assert len(server.peers) == 2
    assert transport._client.is_connected


@pytest.mark.parametrize("refusal", ["500 5.5.2 What", "garbage"])
async def test_stop_never_raises_when_quit_is_refused(refusal: str) -> None:
    logger = RecordingLogger()
    async with ScriptedSmtpServer() as server:
        server.replies["QUIT"] = [refusal]
        transport = smtp_transport(server, logger=logger)
        await transport.start()

        await transport.stop()

    assert not transport._client.is_connected
    assert any("could not quit cleanly: Expected response code" in line for line in logger.records)


async def test_stop_never_raises_when_the_server_hangs_up_at_quit() -> None:
    async with ScriptedSmtpServer() as server:
        server.drop.add("QUIT")
        transport = smtp_transport(server)
        await transport.start()

        await transport.stop()

    assert not transport._client.is_connected


async def test_a_cancelled_stop_still_closes_the_connection() -> None:
    async with ScriptedSmtpServer() as server:
        server.stall.add("QUIT")
        transport = smtp_transport(server)
        await transport.start()

        with anyio.move_on_after(0.2):
            await transport.stop()

    assert not transport._client.is_connected


async def test_the_session_is_restarted_after_the_threshold() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server).set_restart_threshold(2)

        for index in range(3):
            _ = await transport.send(raw(f"Message {index}"), envelope())

    assert server.commands.count("QUIT") == 1
    assert server.commands.index("QUIT") == server.commands.index("DATA", 5) + 1
    assert len(server.peers) == 2


async def test_a_restart_sleeps_between_the_sessions() -> None:
    clock = MockClock()
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server, clock=clock).set_restart_threshold(1, 5)
        start = clock.now().timestamp()

        _ = await transport.send(raw(), envelope())

    assert clock.now().timestamp() - start == pytest.approx(5)
    assert server.commands[-1] == "QUIT"


async def test_a_zero_restart_threshold_keeps_one_session() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server).set_restart_threshold(0)

        for index in range(3):
            _ = await transport.send(raw(f"Message {index}"), envelope())

    assert len(server.peers) == 1


async def test_concurrent_sends_take_turns_on_one_session() -> None:
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server)

        async with anyio.create_task_group() as group:
            for index in range(8):
                _ = group.start_soon(transport.send, raw(f"Message {index}"), envelope())

    assert len(server.peers) == 1
    assert (
        server.commands[1:]
        == [
            "MAIL FROM:<sender@example.org>",
            "RCPT TO:<recipient@example.org>",
            "DATA",
        ]
        * 8
    )
    assert len(server.messages) == 8


async def test_a_cancelled_send_closes_the_session_and_is_no_failure() -> None:
    dispatcher, recorded = recording_dispatcher()
    async with ScriptedSmtpServer() as server:
        server.stall.add("DATA_END")
        transport = smtp_transport(server, event_dispatcher=dispatcher)

        with anyio.move_on_after(0.3):
            _ = await transport.send(raw("Message 1"), envelope())
        connected_after_cancel = transport._client.is_connected
        server.stall.clear()
        _ = await transport.send(raw("Message 2"), envelope())

    assert [type(event) for event in recorded] == [MessageEvent, MessageEvent, SentMessageEvent]
    assert not connected_after_cancel
    assert "RSET" not in server.commands
    assert len(server.peers) == 2


async def test_a_refused_recipient_resets_the_session_for_the_next_email() -> None:
    async with ScriptedSmtpServer() as server:
        server.replies["RCPT"] = ["550 5.1.1 No such user"]
        transport = smtp_transport(server)

        with pytest.raises(Exception, match='got code "550"'):
            _ = await transport.send(raw("Message 1"), envelope())
        _ = await transport.send(raw("Message 2"), envelope())

    assert "RSET" in server.commands
    assert len(server.peers) == 1
    assert server.messages == [b"Message 2\r\n"]


async def test_the_session_is_logged_as_it_starts_and_stops() -> None:
    logger = RecordingLogger()
    async with ScriptedSmtpServer() as server:
        transport = smtp_transport(server, logger=logger)
        name = str(transport)

        await transport.start()
        await transport.stop()

    assert logger.records == [
        f'Email transport "{name}" starting',
        f'Email transport "{name}" started',
        f'Email transport "{name}" stopping',
        f'Email transport "{name}" stopped',
    ]


async def test_the_sent_message_carries_the_exchange() -> None:
    async with ScriptedSmtpServer() as server:
        sent = await smtp_transport(server).send(raw(), envelope())

    assert sent is not None
    assert sent.get_debug() == (
        "< 220 localhost ESMTP ready\n"
        "> HELO [127.0.0.1]\n"
        "< 250 localhost\n"
        "> MAIL FROM:<sender@example.org>\n"
        "< 250 2.0.0 Ok\n"
        "> RCPT TO:<recipient@example.org>\n"
        "< 250 2.0.0 Ok\n"
        "> DATA\n"
        '< 354 End data with "." on a line by itself\n'
        "> [message]\n"
        "< 250 2.0.0 Ok: queued as 1A2B3C\n"
    )
