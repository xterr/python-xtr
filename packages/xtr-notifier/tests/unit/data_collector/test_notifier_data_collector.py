from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

import anyio
import anyio.lowlevel
import pytest
from xtr_clock import MockClock
from xtr_http_kernel.data_collector import ProfiledRequest

from xtr_notifier.data_collector import NotifierDataCollector
from xtr_notifier.event import FailedMessageEvent, MessageEvent, SentMessageEvent
from xtr_notifier.exception import TransportError
from xtr_notifier.message import ChatMessage, SentMessage, SmsMessage

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

# Neither method reads the request: everything comes from the trace.
_PROFILED = ProfiledRequest(
    request=cast("ServerRequestInterface", object()), status_code=200, headers={}, state={}
)
_EMPTY: dict[str, object] = {
    "messages": [],
    "count": 0,
    "queued": 0,
    "sent": 0,
    "failed": 0,
    "by_transport": {},
}


def _collector() -> tuple[NotifierDataCollector, MockClock]:
    clock = MockClock(datetime(2026, 1, 1, tzinfo=UTC))
    return NotifierDataCollector(clock), clock


def _messages(collector: NotifierDataCollector) -> list[dict[str, object]]:
    return cast("list[dict[str, object]]", collector.collect(_PROFILED)["messages"])


def test_the_collector_is_named_notifier() -> None:
    assert NotifierDataCollector().name == "notifier"


def test_nothing_is_recorded_before_a_request_begins() -> None:
    collector, _ = _collector()

    collector.on_message(MessageEvent(ChatMessage("Hi")))

    assert collector.collect(_PROFILED) == _EMPTY


def test_a_sent_message_is_recorded_with_its_outcome_and_duration() -> None:
    collector, clock = _collector()
    collector.begin_request()
    message = ChatMessage("Hi", transport="slack")
    collector.on_message(MessageEvent(message))
    clock.sleep(0.03)

    collector.on_sent_message(
        SentMessageEvent(SentMessage(message, "slack://default", message_id="m-1"))
    )

    [notified] = _messages(collector)
    assert notified["status"] == "sent"
    assert (notified["sent_through"], notified["sent_message_id"]) == ("slack://default", "m-1")
    assert notified["duration_ms"] == pytest.approx(30.0)


def test_a_failed_message_is_recorded_with_its_error() -> None:
    collector, _ = _collector()
    collector.begin_request()
    message = ChatMessage("Hi")
    collector.on_message(MessageEvent(message))

    collector.on_failed_message(FailedMessageEvent(message, TransportError("unreachable")))

    [notified] = _messages(collector)
    assert (notified["status"], notified["error"]) == ("failed", "TransportError: unreachable")


def test_a_failover_attempt_after_a_failure_is_a_message_of_its_own() -> None:
    collector, _ = _collector()
    collector.begin_request()
    message = ChatMessage("Hi", transport="ops")
    collector.on_message(MessageEvent(message))
    collector.on_failed_message(FailedMessageEvent(message, TransportError("down")))
    collector.on_message(MessageEvent(message))

    collector.on_sent_message(SentMessageEvent(SentMessage(message, "fake://backup")))

    assert [notified["status"] for notified in _messages(collector)] == ["failed", "sent"]


def test_a_report_matches_the_very_message_announced_not_an_equal_one() -> None:
    collector, _ = _collector()
    collector.begin_request()
    first, second = ChatMessage("Hi"), ChatMessage("Hi")
    collector.on_message(MessageEvent(first))
    collector.on_message(MessageEvent(second))

    collector.on_sent_message(SentMessageEvent(SentMessage(first, "null")))

    assert [notified["status"] for notified in _messages(collector)] == ["sent", "pending"]


def test_a_queued_message_is_not_completed_by_a_report() -> None:
    collector, _ = _collector()
    collector.begin_request()
    message = SmsMessage("+33123", "Code")
    collector.on_message(MessageEvent(message, queued=True))

    collector.on_sent_message(SentMessageEvent(SentMessage(message, "null")))

    [notified] = _messages(collector)
    assert (notified["queued"], notified["status"]) == (True, "queued")


def test_a_report_for_a_message_never_announced_records_nothing() -> None:
    collector, _ = _collector()
    collector.begin_request()

    collector.on_failed_message(FailedMessageEvent(ChatMessage("Hi"), TransportError("down")))

    assert collector.collect(_PROFILED) == _EMPTY


def test_the_request_s_messages_are_counted_by_status_and_by_transport() -> None:
    collector, _ = _collector()
    collector.begin_request()
    sent, failed = ChatMessage("a", transport="slack"), ChatMessage("b", transport="slack")
    collector.on_message(MessageEvent(sent))
    collector.on_sent_message(SentMessageEvent(SentMessage(sent, "slack://default")))
    collector.on_message(MessageEvent(failed))
    collector.on_failed_message(FailedMessageEvent(failed, TransportError("down")))
    collector.on_message(MessageEvent(SmsMessage("+33123", "c", transport="sms"), queued=True))
    collector.on_message(MessageEvent(ChatMessage("d")))

    data = collector.late_collect(collector.collect(_PROFILED), _PROFILED)

    assert {key: value for key, value in data.items() if key != "messages"} == {
        "count": 4,
        "queued": 1,
        "sent": 1,
        "failed": 1,
        "by_transport": {"slack": 2, "sms": 1},
    }
    assert json.loads(json.dumps(data)) == data


def test_beginning_a_request_starts_from_nothing() -> None:
    collector, _ = _collector()
    collector.begin_request()
    collector.on_message(MessageEvent(ChatMessage("Hi")))

    collector.begin_request()

    assert collector.collect(_PROFILED) == _EMPTY


async def test_concurrent_requests_each_collect_only_their_own_messages() -> None:
    collector, _ = _collector()
    subjects: dict[str, list[object]] = {}

    async def request(name: str, count: int) -> None:
        collector.begin_request()
        for index in range(count):
            collector.on_message(MessageEvent(ChatMessage(f"{name}-{index}")))
            await anyio.lowlevel.checkpoint()
        subjects[name] = [notified["subject"] for notified in _messages(collector)]

    async with anyio.create_task_group() as group:
        _ = group.start_soon(request, "a", 1)
        _ = group.start_soon(request, "b", 3)

    assert subjects == {"a": ["a-0"], "b": ["b-0", "b-1", "b-2"]}
