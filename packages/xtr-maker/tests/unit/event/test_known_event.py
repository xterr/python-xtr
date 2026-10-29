"""Unit tests for :class:`xtr_maker.event.known_event.KnownEvent`."""

from __future__ import annotations

from xtr_maker.event import KnownEvent


def test_a_class_is_referenced_by_its_module_and_name() -> None:
    event = KnownEvent("OrderPlaced", "shop.event")

    assert event.reference == "shop.event:OrderPlaced"
    assert event.label == "OrderPlaced (shop.event)"


def test_an_event_known_by_name_is_referenced_by_that_name() -> None:
    event = KnownEvent("order.placed")

    assert event.reference == "order.placed"
    assert event.label == '"order.placed"'
