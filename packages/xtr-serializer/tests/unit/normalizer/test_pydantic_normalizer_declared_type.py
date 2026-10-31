"""A value handed with the type it was declared with is written as that type, and checked by it."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from tests.fixtures.foreign import Money, Priced
from tests.fixtures.hierarchies import Delivery, Event
from xtr_serializer import InvalidArgumentError, NotNormalizableValueError, PydanticNormalizer

NORMALIZER = PydanticNormalizer()
EUROS = Money(Decimal("12.50"), "EUR")
DELIVERY = Delivery("d", "ana@example.com", datetime(2026, 10, 30, tzinfo=UTC))


def test_a_list_declared_with_its_item_type_is_written_by_it() -> None:
    written = NORMALIZER.normalize([DELIVERY], type_=list[Event])

    assert written == [NORMALIZER.normalize(DELIVERY)]


def test_a_value_of_a_class_without_a_schema_is_written_by_its_declared_annotation() -> None:
    assert NORMALIZER.normalize(EUROS, type_=Priced) == "12.50 EUR"


def test_it_handles_a_value_its_declared_type_has_a_schema_for() -> None:
    assert (
        NORMALIZER.supports_normalization(EUROS),
        NORMALIZER.supports_normalization(EUROS, type_=Priced),
    ) == (False, True)


def test_a_value_outside_its_declared_type_is_refused() -> None:
    with pytest.raises(NotNormalizableValueError):
        _ = NORMALIZER.normalize([EUROS], type_=list[Event])


def test_a_declared_type_without_a_schema_is_refused() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = NORMALIZER.normalize(EUROS, type_=Money)
