"""The adapter of each type, built under the exact configuration, kept for the types used last."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from xtr_serializer.normalizer._adapter_cache import AdapterCache, build_adapter


class Opaque:
    """A class pydantic has no schema for."""


def test_it_gives_the_same_adapter_for_a_type_used_again() -> None:
    cache = AdapterCache()

    assert cache.get(list[int]) is cache.get(list[int])


def test_it_tells_why_a_type_has_no_adapter() -> None:
    assert build_adapter(Opaque) == "pydantic has no schema for 'Opaque'"


def test_an_adapter_reads_strictly_and_refuses_what_is_not_finite() -> None:
    adapter = build_adapter(tuple[int, Decimal])
    assert isinstance(adapter, TypeAdapter)

    with pytest.raises(ValidationError) as raised:
        _ = adapter.validate_json('["1", "NaN"]')

    assert [error["type"] for error in raised.value.errors()] == ["int_type", "finite_number"]
