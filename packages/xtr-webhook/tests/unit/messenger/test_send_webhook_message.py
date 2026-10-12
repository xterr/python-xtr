from __future__ import annotations

import dataclasses

import pytest
from xtr_messenger import name_of
from xtr_remote_event import RemoteEvent

from xtr_webhook.messenger import SendWebhookMessage
from xtr_webhook.subscriber import Subscriber


def _assign(target: object, name: str, value: object) -> None:
    # Taking an `object` keeps the type checkers out of the way. They refuse the
    # assignment on sight, and what is being tested here is that so does the runtime.
    setattr(target, name, value)


def _subscriber() -> Subscriber:
    return Subscriber("https://receiver.test/hook", "s3cr3t")


def _event() -> RemoteEvent:
    return RemoteEvent(name="order.created", id="evt_1", payload={"total": 10})


def test_it_carries_the_subscriber_and_the_event() -> None:
    subscriber, event = _subscriber(), _event()
    message = SendWebhookMessage(subscriber, event)

    assert message.subscriber == subscriber
    assert message.event == event


def test_it_travels_under_a_name_that_outlives_a_move() -> None:
    assert name_of(SendWebhookMessage) == "xtr_webhook.send.v1"


def test_nothing_can_be_changed_after_it_is_dispatched() -> None:
    message = SendWebhookMessage(_subscriber(), _event())

    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(message, "subscriber", Subscriber("https://elsewhere.test/hook", "other"))


def test_it_carries_no_instance_dictionary_to_put_anything_else_in() -> None:
    assert not hasattr(SendWebhookMessage(_subscriber(), _event()), "__dict__")


def test_two_messages_asking_for_the_same_delivery_are_equal() -> None:
    subscriber, event = _subscriber(), _event()

    assert SendWebhookMessage(subscriber, event) == SendWebhookMessage(subscriber, event)


def test_the_secret_it_carries_stays_out_of_its_repr() -> None:
    assert "s3cr3t" not in repr(SendWebhookMessage(_subscriber(), _event()))
