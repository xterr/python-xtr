from __future__ import annotations

import datetime as dt
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from pathlib import PurePosixPath

import pytest

from xtr_logging import Normalizer


class Colour(Enum):
    RED = "red"


@dataclass
class Point:
    x: int
    y: int


class Opaque:
    pass


def _raise(error: Exception) -> None:
    raise error


def _raised(error: Exception) -> Exception:
    try:
        _raise(error)
    except Exception as caught:  # noqa: BLE001 — the point is to capture a traceback
        return caught
    raise AssertionError


@pytest.mark.parametrize("value", [None, True, 3, 1.5, "text"])
def test_json_scalars_pass_through(value: object) -> None:
    assert Normalizer().normalize(value) == value


@pytest.mark.parametrize(
    ("value", "expected"), [(math.nan, "NaN"), (math.inf, "INF"), (-math.inf, "-INF")]
)
def test_non_finite_floats_become_strings(value: float, expected: str) -> None:
    assert Normalizer().normalize(value) == expected


def test_an_enum_becomes_its_value() -> None:
    assert Normalizer().normalize(Colour.RED) == "red"


def test_a_datetime_is_iso_8601_by_default() -> None:
    at = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC)

    assert Normalizer().normalize(at) == "2026-01-02T03:04:05+00:00"


def test_a_datetime_follows_the_date_format_when_given() -> None:
    at = dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC)

    assert Normalizer("%Y/%m/%d").normalize(at) == "2026/01/02"


def test_containers_are_normalised_recursively_with_string_keys() -> None:
    value = {1: (Colour.RED, {"nested": frozenset({2})})}

    assert Normalizer().normalize(value) == {"1": ["red", {"nested": [2]}]}


def test_a_dataclass_becomes_its_fields_under_its_class_name() -> None:
    assert Normalizer().normalize(Point(1, 2)) == {f"{__name__}.Point": {"x": 1, "y": 2}}


def test_objects_with_a_string_form_use_it() -> None:
    assert Normalizer().normalize([Decimal("1.5"), PurePosixPath("/a")]) == ["1.5", "/a"]


def test_objects_without_one_are_named() -> None:
    assert Normalizer().normalize(Opaque()) == f"[object {__name__}.Opaque]"


def test_bytes_are_decoded_without_failing() -> None:
    assert Normalizer().normalize(b"ok\xff") == "ok\\xff"


def test_nesting_past_the_limit_is_cut_short() -> None:
    assert Normalizer(max_depth=1).normalize({"a": {"b": {"c": 1}}}) == {
        "a": {"b": "Over 1 levels deep, aborting normalization"},
    }


def test_collections_past_the_limit_are_cut_short() -> None:
    assert Normalizer(max_items=2).normalize([1, 2, 3]) == [
        1,
        2,
        "Over 2 items (3 total), aborting normalization",
    ]


def test_an_exception_carries_its_class_message_origin_and_cause() -> None:
    cause = ValueError("root")
    error = RuntimeError("outer")
    error.__cause__ = cause

    normalized = Normalizer().normalize(_raised(error))

    assert isinstance(normalized, dict)
    assert normalized["class"] == "RuntimeError"
    assert normalized["message"] == "outer"
    assert re.search(r"test_normalizer\.py:\d+$", str(normalized["file"]))
    assert normalized["previous"] == {"class": "ValueError", "message": "root"}
    assert "trace" not in normalized


def test_an_exception_carries_its_trace_when_asked() -> None:
    normalized = Normalizer(include_stacktraces=True).normalize(_raised(RuntimeError("x")))

    assert isinstance(normalized, dict)
    assert isinstance(normalized["trace"], list)
