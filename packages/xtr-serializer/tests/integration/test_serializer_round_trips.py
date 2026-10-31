"""Values written to JSON by a serializer and read back equal, each part of its exact type."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Final, cast
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from tests.fixtures.foreign import Bill, Charge, Fee, Money, Priced
from tests.fixtures.hierarchies import Batch, Bounce, Complaint, Delivery, Event, Mailbox
from tests.fixtures.orders import Item, Order, Receipt, Shipment, Status
from xtr_serializer import (
    JsonEncoder,
    NotNormalizableValueError,
    PydanticNormalizer,
    Serializer,
    SerializerError,
    ZonedDateTime,
)

AT: Final = datetime(2026, 10, 30, 9, 30, tzinfo=UTC)
# The second 03:30 of the night Bucharest's clocks go back.
REPEATED: Final = datetime(2026, 10, 25, 3, 30, fold=1, tzinfo=ZoneInfo("Europe/Bucharest"))
SERIALIZER: Final = Serializer([PydanticNormalizer()], [JsonEncoder()])

ORDER: Final = Order(
    id=UUID("6f1c2a52-4f0e-4c55-9d7a-2c1f0c3e8b11"),
    placed_at=AT,
    total=Decimal("19.90"),
    status=Status.SHIPPED,
    signature=b"\x00\xff signed",
    dimensions=(1, 2, 3),
    tags=frozenset({"gift", "fragile"}),
    items=[Item(sku="A-1", price=990), Item(sku="B-2", price=1000)],
)
SHIPMENT: Final = Shipment(
    id=UUID("0b8e6c43-27a8-4b8e-9d0c-6a1d5e9f3c20"),
    sent_on=date(2026, 10, 30),
    sent_at=AT,
    transit=timedelta(days=2, hours=3),
    weight=Decimal("1.250"),
    status=Status.OPEN,
    label=b"label",
    route=("Bucharest", "Cluj"),
    zones=frozenset({1, 2}),
)
MAILBOX: Final = Mailbox(
    latest=Batch("batch", events=(Delivery("d", "ana@example.com", AT),), failures=[]),
    failures=[Bounce("b", "full", 552), Complaint("c", "spam", "rude")],
    by_id={"one": Delivery("d", "ion@example.com", AT)},
    maybe=None,
    pair=(Delivery("d", "x@example.com", AT), Complaint("c", "spam")),
)
EUROS: Final = Money(Decimal("12.50"), "EUR")
FEE: Final = Fee("delivery", Money(Decimal("2.5"), "EUR"))
BILL: Final = Bill(total=EUROS, charges=[FEE])


@dataclass(frozen=True)
class Meeting:
    at: ZonedDateTime


def round_trip(value: object, type_: object = None) -> object:
    declared = type(value) if type_ is None else type_
    return SERIALIZER.deserialize(
        SERIALIZER.serialize(value, "json", type_=type_), declared, "json"
    )


@pytest.mark.parametrize(
    "value", [ORDER, SHIPMENT, MAILBOX, BILL], ids=["model", "dataclass", "hierarchies", "foreign"]
)
def test_a_value_reads_back_equal(value: object) -> None:
    assert round_trip(value) == value


def test_a_model_reads_back_as_its_class_typed_as_it() -> None:
    order: Order = SERIALIZER.deserialize(SERIALIZER.serialize(ORDER, "json"), Order, "json")

    assert (type(order.total), type(order.dimensions), type(order.items[0])) == (
        Decimal,
        tuple,
        Item,
    )


def test_values_of_a_hierarchy_read_back_as_their_exact_classes() -> None:
    read = cast("Mailbox", round_trip(MAILBOX))

    assert [type(failure) for failure in read.failures] == [Bounce, Complaint]


def test_a_value_of_a_hierarchy_written_alone_reads_back_through_its_base() -> None:
    delivery = Delivery("d", "ana@example.com", AT)

    read = SERIALIZER.deserialize(SERIALIZER.serialize(delivery, "json"), Event, "json")

    assert (read, type(read)) == (delivery, Delivery)


def test_a_zoned_datetime_in_a_repeated_hour_reads_back_with_its_zone_and_fold() -> None:
    read = cast("Meeting", round_trip(Meeting(REPEATED)))

    assert (read.at, read.at.tzinfo, read.at.fold) == (REPEATED, REPEATED.tzinfo, 1)


def test_a_decimal_reads_back_with_its_digits() -> None:
    assert str(cast("Shipment", round_trip(SHIPMENT)).weight) == "1.250"


def test_money_annotated_with_how_it_is_written_reads_back_inside_a_hierarchy() -> None:
    read = cast("Bill", round_trip(BILL))

    assert (type(read.charges[0]), cast("Fee", read.charges[0]).price) == (Fee, FEE.price)


def test_money_written_alone_reads_back_through_its_annotation() -> None:
    assert round_trip(EUROS, Priced) == EUROS


def test_a_list_of_values_of_a_hierarchy_reads_back_through_its_declared_type() -> None:
    charges = [Fee("a", EUROS), Fee("b", Money(Decimal(1), "USD"))]

    assert round_trip(charges, list[Charge]) == charges


@pytest.mark.parametrize("value", [[1, "a", None, {"b": [True, 1.5]}], {"a": {"b": []}}])
def test_a_list_or_dict_of_plain_data_reads_back_without_a_declared_type(value: object) -> None:
    assert round_trip(value) == value


def test_a_typed_dict_reads_back_through_its_declared_type() -> None:
    receipt = Receipt(number=1, issued_at=AT, seal=b"\x01")

    assert round_trip(receipt, Receipt) == receipt


def test_a_dict_of_values_of_a_hierarchy_reads_back_through_its_declared_type() -> None:
    events = {"one": Delivery("d", "ana@example.com", AT), "two": Event("e")}

    read = cast("dict[str, Event]", round_trip(events, dict[str, Event]))

    assert (read, type(read["one"])) == (events, Delivery)


@pytest.mark.parametrize(
    "value", [[SHIPMENT], {"order": ORDER}, [(1, 2)]], ids=["list", "dict", "tuple"]
)
def test_a_container_of_what_is_not_plain_data_is_refused_without_a_declared_type(
    value: object,
) -> None:
    with pytest.raises(NotNormalizableValueError):
        _ = SERIALIZER.serialize(value, "json")


def test_a_value_outside_its_declared_type_is_refused() -> None:
    with pytest.raises(NotNormalizableValueError):
        _ = SERIALIZER.serialize([ORDER], "json", type_=list[Shipment])


HOSTILE: Final = [
    "",
    "nan",
    "{",
    "[" * 10_000 + "]" * 10_000,
    "1" * 5_000,
    '"\\ud800"',
    b"\xff\xfe",
    '{"total": "1 EURO", "charges": []}',
    '{"total": "NaN EUR", "charges": []}',
    '{"total": 12, "charges": []}',
    '{"total": "1 EUR", "charges": [{"$type": "nope", "label": "x"}]}',
    '{"total": "1 EUR", "charges": [{"$type": "delivery", "label": "x"}]}',
    '{"total": "1 EUR", "charges": [{"label": "x", "price": "1 EUR"}]}',
    '{"total": "1 EUR", "charges": {"$type": "fee"}}',
    '{"__class__": "os.system"}',
]


@pytest.mark.parametrize("text", HOSTILE)
def test_text_from_the_wire_that_does_not_hold_a_bill_raises_only_serializer_errors(
    text: str | bytes,
) -> None:
    with pytest.raises(SerializerError) as raised:
        _ = SERIALIZER.deserialize(text, Bill, "json")

    assert type(raised.value).__module__.startswith("xtr_serializer.")


def test_threads_sharing_a_serializer_each_read_back_what_they_wrote() -> None:
    values: list[object] = [ORDER, SHIPMENT, MAILBOX, BILL, Meeting(REPEATED)] * 2
    read: list[object] = [None] * len(values)

    def run(index: int) -> None:
        for _ in range(20):
            read[index] = round_trip(values[index])

    threads = [threading.Thread(target=run, args=(index,)) for index in range(len(values))]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert read == values
