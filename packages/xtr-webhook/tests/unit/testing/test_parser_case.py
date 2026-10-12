from __future__ import annotations

import dataclasses

import pytest
from xtr_remote_event import RemoteEvent

from xtr_webhook.testing import ParserCase


def test_it_carries_the_payload_and_what_it_must_become() -> None:
    case = ParserCase("order_paid.json", b"{}", RemoteEvent("order.paid", "ord_1", {}))

    assert case.id == "order_paid.json"
    assert case.payload == b"{}"
    assert case.expected == RemoteEvent("order.paid", "ord_1", {})


def test_it_holds_every_event_of_a_batched_payload() -> None:
    expected = [RemoteEvent("a", "1", {}), RemoteEvent("b", "2", {})]

    assert ParserCase("batch.json", b"{}", expected).expected == expected


def test_it_cannot_be_changed_once_read_off_disk() -> None:
    case = ParserCase("order_paid.json", b"{}", RemoteEvent("order.paid", "ord_1", {}))

    with pytest.raises(dataclasses.FrozenInstanceError):
        # Through the name: a plain assignment is what both type checkers refuse
        # outright, which is the runtime refusal being proved here.
        setattr(case, "id", "other.json")  # noqa: B010


def test_it_keeps_no_instance_dictionary() -> None:
    case = ParserCase("order_paid.json", b"{}", RemoteEvent("order.paid", "ord_1", {}))

    assert not hasattr(case, "__dict__")


def test_two_cases_read_off_the_same_files_are_equal() -> None:
    event = RemoteEvent("order.paid", "ord_1", {})

    assert ParserCase("a.json", b"{}", event) == ParserCase("a.json", b"{}", event)
