from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from xtr_remote_event.event.mailer import (
    AbstractMailerEvent,
    MailerDeliveryEvent,
    MailerEngagementEvent,
)

_DATE = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)


def _assign(target: object, name: str, value: object) -> None:
    # Taking an `object` keeps the type checkers out of the way. They refuse the
    # assignment on sight, and what is being tested here is that so does the runtime.
    setattr(target, name, value)


def _click(url: str = "https://example.com/offer") -> MailerEngagementEvent:
    return MailerEngagementEvent(
        MailerEngagementEvent.CLICK,
        "evt_1",
        {"event": "clicked", "url": url},
        date=_DATE,
        recipient_email="jane@example.com",
        metadata={"order_id": "7"},
        tags=("newsletter",),
    )


def test_it_carries_what_the_provider_reported() -> None:
    event = _click()

    assert event.name == "click"
    assert event.id == "evt_1"
    assert event.payload == {"event": "clicked", "url": "https://example.com/offer"}
    assert event.date == _DATE
    assert event.recipient_email == "jane@example.com"
    assert event.metadata == {"order_id": "7"}
    assert event.tags == ("newsletter",)


def test_it_is_a_mailer_event() -> None:
    assert isinstance(_click(), AbstractMailerEvent)


def test_two_reports_of_the_same_engagement_are_equal() -> None:
    assert _click() == _click()


def test_reports_differing_in_their_payload_are_not_equal() -> None:
    assert _click("https://example.com/offer") != _click("https://example.com/unsubscribe")


def test_it_never_equals_a_delivery_report_carrying_the_same_fields() -> None:
    delivery = MailerDeliveryEvent(
        MailerEngagementEvent.CLICK,
        "evt_1",
        {"event": "clicked", "url": "https://example.com/offer"},
        date=_DATE,
        recipient_email="jane@example.com",
        metadata={"order_id": "7"},
        tags=("newsletter",),
    )

    assert _click() != delivery


def test_nothing_can_be_changed_after_the_fact() -> None:
    event = _click()

    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(event, "recipient_email", "john@example.com")


@pytest.mark.parametrize(
    ("constant", "value"),
    [
        (MailerEngagementEvent.OPEN, "open"),
        (MailerEngagementEvent.CLICK, "click"),
        (MailerEngagementEvent.SPAM, "spam"),
        (MailerEngagementEvent.UNSUBSCRIBE, "unsubscribe"),
    ],
)
def test_each_constant_names_what_the_recipient_did(constant: str, value: str) -> None:
    assert constant == value


def test_the_constants_are_not_fields_of_the_event() -> None:
    assert [field.name for field in dataclasses.fields(MailerEngagementEvent)] == [
        "name",
        "id",
        "payload",
        "date",
        "recipient_email",
        "metadata",
        "tags",
    ]
