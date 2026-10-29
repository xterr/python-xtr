"""pydantic's errors become this package's, located, with extra fields grouped per object."""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_core import ErrorDetails

from xtr_serializer.exception import ExtraAttributesError, NotNormalizableValueError
from xtr_serializer.normalizer._validation_refusals import refusals_of

PLANTED_VALUE = "s3cr3t-t0ken-4f9a"


class Line(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", strict=True)

    price: int


class Basket(BaseModel):
    lines: list[Line]


def details_of(data: object) -> ValidationError:
    with pytest.raises(ValidationError) as raised:
        _ = Basket.model_validate(data)
    return raised.value


def test_a_value_that_does_not_fit_keeps_its_path_type_and_message() -> None:
    data = {"lines": [{"price": "1"}]}
    error = details_of(data)

    [refusal] = refusals_of(error.errors(), data)

    assert type(refusal) is NotNormalizableValueError
    assert (refusal.path, refusal.error_type, refusal.current_type) == (
        "lines[0].price",
        "int_type",
        "str",
    )
    assert refusal.message == "Input should be a valid integer"


def test_the_extra_fields_of_one_object_are_one_error() -> None:
    data = {"lines": [{"price": 1, "a": 0, "b": 0}, {"price": 1, "c": 0}]}
    error = details_of(data)

    refusals = refusals_of(error.errors(), data)

    assert [
        (refusal.path, refusal.extra_attributes)
        for refusal in refusals
        if isinstance(refusal, ExtraAttributesError)
    ] == [("lines[0]", ("a", "b")), ("lines[1]", ("c",))]
    assert len(refusals) == 2


@pytest.mark.parametrize(
    "error_type",
    [
        "union_tag_invalid",
        "bytes_invalid_encoding",
        "value_error",
        "assertion_error",
        "get_attribute_error",
        "iteration_error",
        "mapping_type",
        "datetime_object_invalid",
        "timezone_offset",
    ],
)
def test_a_message_pydantic_builds_from_the_data_is_replaced(error_type: str) -> None:
    detail = ErrorDetails(
        type=error_type, loc=("x",), msg=f"refused {PLANTED_VALUE}", input=PLANTED_VALUE
    )

    [refusal] = refusals_of([detail], {"x": PLANTED_VALUE})

    assert PLANTED_VALUE not in refusal.message
    assert (refusal.path, refusal.error_type) == ("x", error_type)
