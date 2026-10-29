"""Plain data is exactly what JSON holds, nested to any depth."""

from __future__ import annotations

from typing import get_args

from xtr_serializer import NormalizedValue


def test_it_is_one_of_the_kinds_of_value_json_holds() -> None:
    assert get_args(NormalizedValue) == (
        bool,
        int,
        float,
        str,
        list["NormalizedValue"],
        dict[str, "NormalizedValue"],
        type(None),
    )
