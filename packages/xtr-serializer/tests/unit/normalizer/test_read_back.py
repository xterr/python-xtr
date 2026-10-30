"""Written data read back and compared, so what would come back changed is refused."""

from __future__ import annotations

import traceback
from datetime import UTC, datetime
from decimal import Decimal
from typing import NoReturn

from pydantic import ConfigDict, TypeAdapter
from xtr_clock import DatePoint

from xtr_serializer.normalizer._read_back import read_back_refusal

DECIMALS: TypeAdapter[list[Decimal]] = TypeAdapter(list[Decimal])
ANYTHING: TypeAdapter[list[object]] = TypeAdapter(list[object])
PLANTED_VALUE = "s3cr3t-t0ken-4f9a"


def test_data_that_reads_back_equal_is_not_refused() -> None:
    assert read_back_refusal([Decimal("1.5")], ["1.5"], DECIMALS.validate_json) is None


def test_data_that_does_not_read_back_is_refused_where_reading_stops() -> None:
    refusal = read_back_refusal([Decimal(1), Decimal("NaN")], ["1", "NaN"], DECIMALS.validate_json)

    assert refusal is not None
    assert (refusal.path, refusal.error_type) == ("[1]", "finite_number")
    assert refusal.message == "it would not read back: Input should be a finite number"


def test_infinity_is_read_as_itself_and_refused_rather_than_read_as_null() -> None:
    floats: TypeAdapter[list[float | None]] = TypeAdapter(
        list[float | None], config=ConfigDict(allow_inf_nan=False)
    )

    refusal = read_back_refusal([float("inf")], [float("inf")], floats.validate_json)

    assert refusal is not None
    assert refusal.error_type == "finite_number"


def test_data_that_reads_back_changed_is_refused_where_it_first_differs() -> None:
    refusal = read_back_refusal([1, (1, 2)], [1, [1, 2]], ANYTHING.validate_json)

    assert refusal is not None
    assert (refusal.path, refusal.error_type, refusal.current_type) == ("[1]", "not_exact", "tuple")


def test_a_value_reading_back_equal_as_another_type_is_refused() -> None:
    ints: TypeAdapter[dict[str, int]] = TypeAdapter(dict[str, int])

    refusal = read_back_refusal({"a": 1, "b": True}, {"a": 1, "b": 1}, ints.validate_json)

    assert refusal is not None
    assert (refusal.path, refusal.current_type) == ("b", "bool")


def test_a_set_member_reading_back_as_another_type_is_refused_at_the_set() -> None:
    ints: TypeAdapter[list[frozenset[int]]] = TypeAdapter(list[frozenset[int]])

    refusal = read_back_refusal([frozenset({True})], [[1]], ints.validate_json)

    assert refusal is not None
    assert (refusal.path, refusal.current_type) == ("[0]", "bool")


def test_a_datetime_subclass_may_read_back_as_a_datetime() -> None:
    datetimes: TypeAdapter[list[datetime]] = TypeAdapter(list[datetime])
    point = DatePoint(2026, 1, 1, tzinfo=UTC)

    assert read_back_refusal([point], ["2026-01-01T00:00:00Z"], datetimes.validate_json) is None


def test_written_data_with_no_json_form_is_refused_without_quoting_it() -> None:
    text = f"\ud800{PLANTED_VALUE}"

    refusal = read_back_refusal([text], [text], ANYTHING.validate_json)

    assert refusal is not None
    assert refusal.error_type == "not_json"
    assert PLANTED_VALUE not in "".join(traceback.format_exception(refusal))


def fail_to_read(_text: bytes) -> NoReturn:
    raise KeyError(PLANTED_VALUE)


def test_a_read_that_raises_is_refused_naming_only_what_it_raised() -> None:
    refusal = read_back_refusal([1], [1], fail_to_read)

    assert refusal is not None
    assert refusal.error_type == "not_read_back"
    assert "KeyError" in refusal.message
    assert PLANTED_VALUE not in refusal.message


def test_a_comparison_that_raises_is_refused_where_it_raised() -> None:
    def read_signalling_nan(_text: bytes) -> list[Decimal]:
        return [Decimal(1), Decimal("sNaN")]

    refusal = read_back_refusal([Decimal(1), Decimal("sNaN")], ["1", "sNaN"], read_signalling_nan)

    assert refusal is not None
    assert (refusal.path, refusal.error_type) == ("[1]", "not_comparable")
