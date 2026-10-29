"""What a normalizer handles is keyed by class or wildcard, valued by what its answer rests on."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Literal, get_args, get_origin

from xtr_serializer import SupportedTypes


def test_it_maps_classes_and_the_two_wildcards_to_whether_the_answer_is_kept() -> None:
    assert get_origin(SupportedTypes) is Mapping
    assert get_args(SupportedTypes) == (type | Literal["*", "object"], bool | None)
