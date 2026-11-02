from __future__ import annotations

import dataclasses

import pytest
from xtr_serializer import ClassDiscriminatorMapping

from tests.fixtures.events import DeliveryReport, StrayNotice
from xtr_remote_event import RemoteEvent


def _assign(target: object, name: str, value: object) -> None:
    # Taking an `object` keeps the type checkers out of the way. They refuse the
    # assignment on sight, and what is being tested here is that so does the runtime.
    setattr(target, name, value)


def test_it_carries_where_it_came_from_its_id_and_the_payload() -> None:
    event = RemoteEvent("payment.captured", "evt_1", {"amount": 500})

    assert event.name == "payment.captured"
    assert event.id == "evt_1"
    assert event.payload == {"amount": 500}


def test_two_events_describing_the_same_thing_are_equal() -> None:
    assert RemoteEvent("payment.captured", "evt_1", {"amount": 500}) == RemoteEvent(
        "payment.captured", "evt_1", {"amount": 500}
    )


def test_events_differing_in_one_field_are_not_equal() -> None:
    assert RemoteEvent("payment.captured", "evt_1", {}) != RemoteEvent(
        "payment.captured", "evt_2", {}
    )


def test_nothing_can_be_changed_after_the_fact() -> None:
    event = RemoteEvent("payment.captured", "evt_1", {})

    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(event, "name", "payment.refunded")


def test_it_is_the_base_of_a_hierarchy_tagged_under_dollar_type() -> None:
    mapping = ClassDiscriminatorMapping.for_class(RemoteEvent)

    assert mapping is not None
    assert mapping.type_property == "$type"


def test_a_plain_event_is_written_under_its_own_name() -> None:
    mapping = ClassDiscriminatorMapping.for_class(RemoteEvent)

    assert mapping is not None
    assert mapping.types_mapping["remote_event"] is RemoteEvent


def test_an_application_event_joins_the_hierarchy_under_the_name_it_registered() -> None:
    mapping = ClassDiscriminatorMapping.for_class(RemoteEvent)

    assert mapping is not None
    assert mapping.types_mapping["test_delivery_report"] is DeliveryReport


def test_a_class_of_another_hierarchy_is_no_remote_event() -> None:
    mapping = ClassDiscriminatorMapping.for_class(RemoteEvent)

    assert mapping is not None
    assert StrayNotice not in mapping.types_mapping.values()
