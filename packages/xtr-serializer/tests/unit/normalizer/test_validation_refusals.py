"""pydantic's errors become this package's, located, with extra fields grouped per object."""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from xtr_serializer.exception import ExtraAttributesError, NotNormalizableValueError
from xtr_serializer.normalizer._validation_refusals import refusals_of


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
    error = details_of({"lines": [{"price": "1"}]})

    [refusal] = refusals_of(error.errors())

    assert type(refusal) is NotNormalizableValueError
    assert (refusal.path, refusal.error_type, refusal.current_type) == (
        "lines[0].price",
        "int_type",
        "str",
    )
    assert refusal.message == "Input should be a valid integer"


def test_the_extra_fields_of_one_object_are_one_error() -> None:
    error = details_of({"lines": [{"price": 1, "a": 0, "b": 0}, {"price": 1, "c": 0}]})

    refusals = refusals_of(error.errors())

    assert [
        (refusal.path, refusal.extra_attributes)
        for refusal in refusals
        if isinstance(refusal, ExtraAttributesError)
    ] == [("lines[0]", ("a", "b")), ("lines[1]", ("c",))]
    assert len(refusals) == 2
