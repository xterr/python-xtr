"""The check plain data passes to be written as JSON, shared by the encoder and the normalizer."""

from __future__ import annotations

import math

import pytest
from pydantic import TypeAdapter, ValidationError

from xtr_serializer import NormalizedValue
from xtr_serializer._plain_data import PLAIN_DATA


def test_it_checks_data_against_the_plain_data_type() -> None:
    assert PLAIN_DATA.core_schema == TypeAdapter(NormalizedValue).core_schema


@pytest.mark.parametrize(
    ("data", "error_type"),
    [([math.inf], "finite_number"), ((1, 2), "invalid-json-value")],
    ids=["infinity", "tuple"],
)
def test_it_refuses_what_json_has_no_form_for(data: object, error_type: str) -> None:
    with pytest.raises(ValidationError) as raised:
        _ = PLAIN_DATA.validate_python(data)

    assert raised.value.errors()[0]["type"] == error_type
