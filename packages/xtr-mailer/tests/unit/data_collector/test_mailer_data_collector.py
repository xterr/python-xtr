from __future__ import annotations

from typing import TYPE_CHECKING, cast

import anyio
import pytest
from xtr_http_kernel.data_collector import (
    DataCollectorInterface,
    LateDataCollectorInterface,
    ProfiledRequest,
    TracingDataCollectorInterface,
)
from xtr_mime import Email

from xtr_mailer import Envelope, SentMessage
from xtr_mailer.data_collector import MailerDataCollector
from xtr_mailer.event import FailedMessageEvent, MessageEvent, SentMessageEvent
from xtr_mailer.exception import TransportError

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface

pytestmark = pytest.mark.anyio

_PROFILED = ProfiledRequest(
    request=cast("ServerRequestInterface", object()), status_code=200, headers={}, state={}
)


def _event(subject: str = "Hi", queued: bool = False) -> MessageEvent:
    email = Email().from_("shop@example.com").to("customer@example.com").subject(subject).text("x")
    return MessageEvent(email, Envelope.create(email), "null://", queued=queued)


def _sent(event: MessageEvent) -> SentMessageEvent:
    return SentMessageEvent(SentMessage(event.get_message(), event.get_envelope()))


def _messages(collector: MailerDataCollector) -> list[dict[str, object]]:
    messages = collector.late_collect({}, _PROFILED)["messages"]
    assert isinstance(messages, list)
    return cast("list[dict[str, object]]", messages)


def test_it_is_a_tracing_late_collector_named_mailer() -> None:
    collector = MailerDataCollector()

    assert collector.name == "mailer"
    assert isinstance(collector, DataCollectorInterface)
    assert isinstance(collector, LateDataCollectorInterface)
    assert isinstance(collector, TracingDataCollectorInterface)


def test_outside_a_profiled_request_nothing_is_recorded() -> None:
    collector = MailerDataCollector()
    event = _event()

    collector.on_message(event)
    collector.on_sent(_sent(event))
    collector.on_failed(FailedMessageEvent(event.get_message(), TransportError("down")))

    assert collector.late_collect({}, _PROFILED) == {
        "messages": [],
        "count": 0,
        "queued": 0,
        "sent": 0,
        "failed": 0,
    }


def test_collect_returns_the_counts_so_far() -> None:
    collector = MailerDataCollector()
    collector.begin_request()
    sent, queued = _event(), _event(queued=True)
    collector.on_message(sent)
    collector.on_message(queued)
    collector.on_sent(_sent(sent))

    assert collector.collect(_PROFILED) == {"count": 2, "queued": 1, "sent": 1, "failed": 0}


def test_an_email_announced_and_not_yet_sent_is_pending() -> None:
    collector = MailerDataCollector()
    collector.begin_request()

    collector.on_message(_event())

    [message] = _messages(collector)
    assert message["status"] == "pending"


def test_a_sent_email_is_marked_sent_with_its_message_id() -> None:
    collector = MailerDataCollector()
    collector.begin_request()
    event = _event()
    collector.on_message(event)
    sent = _sent(event)

    collector.on_sent(sent)

    [message] = _messages(collector)
    assert message["status"] == "sent"
    assert message["message_id"] == sent.get_message().get_message_id()


def test_a_failed_email_is_marked_failed_with_the_error() -> None:
    collector = MailerDataCollector()
    collector.begin_request()
    event = _event()
    collector.on_message(event)

    collector.on_failed(FailedMessageEvent(event.get_message(), TransportError("Server down.")))

    [message] = _messages(collector)
    assert (message["status"], message["error"]) == ("failed", "Server down.")
    assert collector.collect(_PROFILED)["failed"] == 1


def test_a_rejected_email_is_marked_rejected() -> None:
    collector = MailerDataCollector()
    collector.begin_request()
    event = _event()
    collector.on_message(event)

    event.reject()

    [message] = _messages(collector)
    assert message["status"] == "rejected"


def test_a_send_is_matched_to_the_announcement_of_the_same_message() -> None:
    collector = MailerDataCollector()
    collector.begin_request()
    first, second = _event("First"), _event("Second")
    collector.on_message(first)
    collector.on_message(second)

    collector.on_sent(_sent(first))
    collector.on_failed(FailedMessageEvent(second.get_message(), TransportError("down")))

    statuses = [(message["subject"], message["status"]) for message in _messages(collector)]
    assert statuses == [("First", "sent"), ("Second", "failed")]


def test_a_send_of_a_message_never_announced_is_ignored() -> None:
    collector = MailerDataCollector()
    collector.begin_request()
    collector.on_message(_event())

    collector.on_sent(_sent(_event()))

    [message] = _messages(collector)
    assert message["status"] == "pending"


def test_beginning_a_request_starts_from_nothing() -> None:
    collector = MailerDataCollector()
    collector.begin_request()
    collector.on_message(_event())

    collector.begin_request()

    assert collector.collect(_PROFILED)["count"] == 0


async def test_requests_served_at_once_each_see_their_own_emails() -> None:
    collector = MailerDataCollector()
    both_recorded = anyio.Event()
    started = 0
    seen: dict[str, list[object]] = {}

    async def request(subject: str) -> None:
        nonlocal started
        collector.begin_request()
        collector.on_message(_event(subject))
        started += 1
        if started == 2:
            both_recorded.set()
        await both_recorded.wait()
        seen[subject] = [message["subject"] for message in _messages(collector)]

    async with anyio.create_task_group() as group:
        _ = group.start_soon(request, "A")
        _ = group.start_soon(request, "B")

    assert seen == {"A": ["A"], "B": ["B"]}
