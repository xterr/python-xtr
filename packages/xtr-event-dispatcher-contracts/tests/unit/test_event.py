from __future__ import annotations

from dataclasses import dataclass

from xtr_event_dispatcher_contracts import Event, StoppableEventInterface


@dataclass(frozen=True)
class _FrozenEvent(Event):
    order_id: int


@dataclass(slots=True)
class _SlottedEvent(Event):
    order_id: int


def test_an_event_starts_unstopped() -> None:
    assert not Event().is_propagation_stopped()


def test_stopping_an_event_is_seen_by_the_next_check() -> None:
    event = Event()

    event.stop_propagation()

    assert event.is_propagation_stopped()


def test_stopping_one_event_leaves_another_running() -> None:
    stopped = Event()
    other = Event()

    stopped.stop_propagation()

    assert not other.is_propagation_stopped()


def test_a_frozen_dataclass_event_can_be_stopped() -> None:
    event = _FrozenEvent(42)

    event.stop_propagation()

    assert event.is_propagation_stopped()


def test_a_slotted_dataclass_event_can_be_stopped() -> None:
    event = _SlottedEvent(42)

    event.stop_propagation()

    assert event.is_propagation_stopped()


def test_an_event_is_a_stoppable_event() -> None:
    assert isinstance(Event(), StoppableEventInterface)
