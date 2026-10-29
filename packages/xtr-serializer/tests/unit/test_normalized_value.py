"""Plain data is pydantic's own JSON value type, the one the JSON encoder checks data against."""

from __future__ import annotations

from pydantic import JsonValue, TypeAdapter

from xtr_serializer import NormalizedValue
from xtr_serializer.encoder import json_encoder


def test_it_is_pydantics_json_value_type() -> None:
    assert NormalizedValue is JsonValue


def test_the_json_encoder_checks_data_against_it() -> None:
    assert json_encoder._JSON_VALUE.core_schema == TypeAdapter(NormalizedValue).core_schema
