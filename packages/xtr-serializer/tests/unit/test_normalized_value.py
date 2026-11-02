"""Plain data is pydantic's own JSON value type."""

from __future__ import annotations

from pydantic import JsonValue

from xtr_serializer import NormalizedValue


def test_it_is_pydantics_json_value_type() -> None:
    assert NormalizedValue is JsonValue
