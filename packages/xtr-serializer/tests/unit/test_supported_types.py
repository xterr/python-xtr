"""What a normalizer handles is keyed by class or wildcard, valued by what its answer rests on."""

from __future__ import annotations

from typing import Final

import pytest
from pydantic import ConfigDict, TypeAdapter, ValidationError

from xtr_serializer import SupportedTypes

SUPPORTED_TYPES: Final[TypeAdapter[SupportedTypes]] = TypeAdapter(
    SupportedTypes, config=ConfigDict(strict=True)
)


def test_it_keys_a_class_or_a_wildcard_to_whether_the_answer_can_be_kept() -> None:
    reported = {int: True, "*": False, "object": None}

    assert SUPPORTED_TYPES.validate_python(reported) == reported


@pytest.mark.parametrize(
    "reported",
    [{"int": True}, {"any": True}, {1: True}],
    ids=["class-name", "other-wildcard", "not-a-class"],
)
def test_a_key_is_a_class_or_one_of_the_two_wildcards(reported: object) -> None:
    with pytest.raises(ValidationError):
        _ = SUPPORTED_TYPES.validate_python(reported)


@pytest.mark.parametrize("answer", [1, "yes"], ids=repr)
def test_an_answer_is_a_bool_or_none(answer: object) -> None:
    with pytest.raises(ValidationError):
        _ = SUPPORTED_TYPES.validate_python({int: answer})
