from __future__ import annotations

import dataclasses

import pytest
from xtr_messenger import name_of

from xtr_remote_event import RemoteEvent
from xtr_remote_event.messenger import ConsumeRemoteEventMessage


def _assign(target: object, name: str, value: object) -> None:
    # Taking an `object` keeps the type checkers out of the way. They refuse the
    # assignment on sight, and what is being tested here is that so does the runtime.
    setattr(target, name, value)


def test_it_carries_the_source_and_the_event() -> None:
    event = RemoteEvent("stripe", "evt_1", {"amount": 500})
    message = ConsumeRemoteEventMessage("stripe", event)

    assert message.type == "stripe"
    assert message.event == event


def test_it_travels_under_a_name_that_outlives_a_move() -> None:
    assert name_of(ConsumeRemoteEventMessage) == "xtr_remote_event.consume.v1"


def test_nothing_can_be_changed_after_it_is_dispatched() -> None:
    message = ConsumeRemoteEventMessage("stripe", RemoteEvent("stripe", "evt_1", {}))

    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(message, "type", "mailgun")


def test_two_messages_asking_for_the_same_work_are_equal() -> None:
    event = RemoteEvent("stripe", "evt_1", {"amount": 500})

    assert ConsumeRemoteEventMessage("stripe", event) == ConsumeRemoteEventMessage("stripe", event)
