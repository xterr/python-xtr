from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

import pytest

from xtr_remote_event.event.mailer import AbstractMailerEvent, MailerDeliveryEvent

_DATE = datetime(2026, 1, 1, 9, 30, tzinfo=UTC)


def _assign(target: object, name: str, value: object) -> None:
    # Taking an `object` keeps the type checkers out of the way. They refuse the
    # assignment on sight, and what is being tested here is that so does the runtime.
    setattr(target, name, value)


def _bounce(reason: str = "550 No such user") -> MailerDeliveryEvent:
    return MailerDeliveryEvent(
        MailerDeliveryEvent.BOUNCE,
        "evt_1",
        {"event": "failed"},
        date=_DATE,
        recipient_email="jane@example.com",
        metadata={"order_id": "7"},
        tags=("receipt",),
        reason=reason,
    )


def test_it_carries_what_the_provider_reported() -> None:
    event = _bounce()

    assert event.name == "bounce"
    assert event.id == "evt_1"
    assert event.payload == {"event": "failed"}
    assert event.date == _DATE
    assert event.recipient_email == "jane@example.com"
    assert event.metadata == {"order_id": "7"}
    assert event.tags == ("receipt",)
    assert event.reason == "550 No such user"


def test_the_reason_is_empty_unless_given() -> None:
    event = MailerDeliveryEvent(MailerDeliveryEvent.DELIVERED, "evt_1", {}, date=_DATE)

    assert event.reason == ""


def test_it_is_a_mailer_event() -> None:
    assert isinstance(_bounce(), AbstractMailerEvent)


def test_two_reports_of_the_same_delivery_are_equal() -> None:
    assert _bounce() == _bounce()


def test_reports_differing_in_their_reason_are_not_equal() -> None:
    assert _bounce("550 No such user") != _bounce("552 Mailbox full")


def test_nothing_can_be_changed_after_the_fact() -> None:
    event = _bounce()

    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(event, "reason", "")


@pytest.mark.parametrize(
    ("constant", "value"),
    [
        (MailerDeliveryEvent.RECEIVED, "received"),
        (MailerDeliveryEvent.DROPPED, "dropped"),
        (MailerDeliveryEvent.DELIVERED, "delivered"),
        (MailerDeliveryEvent.DEFERRED, "deferred"),
        (MailerDeliveryEvent.BOUNCE, "bounce"),
    ],
)
def test_each_constant_names_what_became_of_the_message(constant: str, value: str) -> None:
    assert constant == value


def test_the_constants_are_not_fields_of_the_event() -> None:
    assert [field.name for field in dataclasses.fields(MailerDeliveryEvent)] == [
        "name",
        "id",
        "payload",
        "date",
        "recipient_email",
        "metadata",
        "tags",
        "reason",
    ]
