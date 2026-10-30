"""Written data read back and compared, so what would come back changed is refused."""

from __future__ import annotations

import inspect
import sys
import traceback
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, NoReturn

import pytest
from pydantic import ConfigDict, TypeAdapter
from xtr_clock import DatePoint

from tests.fixtures.nameless import NamelessError, NamelessThing, names_refused
from xtr_serializer.normalizer._read_back import read_back_refusal

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_serializer.exception import NotNormalizableValueError
    from xtr_serializer.normalized_value import NormalizedValue

DECIMALS: TypeAdapter[list[Decimal]] = TypeAdapter(list[Decimal])
ANYTHING: TypeAdapter[list[object]] = TypeAdapter(list[object])
PLANTED_VALUE = "s3cr3t-t0ken-4f9a"


def refusal_of(
    value: object, written: NormalizedValue, read: Callable[[bytes], object] | None
) -> NotNormalizableValueError | None:
    return read_back_refusal(value, written, read, by_alias=True)


def test_data_that_reads_back_equal_is_not_refused() -> None:
    assert refusal_of([Decimal("1.5")], ["1.5"], DECIMALS.validate_json) is None


def test_data_that_does_not_read_back_is_refused_where_reading_stops() -> None:
    refusal = refusal_of([Decimal(1), Decimal("NaN")], ["1", "NaN"], DECIMALS.validate_json)

    assert refusal is not None
    assert (refusal.path, refusal.error_type) == ("[1]", "finite_number")
    assert refusal.message == "it would not read back: Input should be a finite number"


FLOATS: TypeAdapter[dict[str, object]] = TypeAdapter(
    dict[str, object], config=ConfigDict(allow_inf_nan=True)
)


@pytest.mark.parametrize("read", [FLOATS.validate_json, None], ids=["read-back", "partial-write"])
def test_written_data_json_has_no_form_for_is_refused_where_it_sits_whatever_reads_it(
    read: Callable[[bytes], object] | None,
) -> None:
    written: NormalizedValue = {"dict": 1, "x": {"y": [0.5, float("inf")]}}

    refusal = refusal_of(written, written, read)

    assert refusal is not None
    assert (refusal.path, refusal.error_type) == ("x.y[1]", "finite_number")
    assert refusal.message == "it has no JSON form: Input should be a finite number"


def test_a_partial_write_with_a_json_form_is_not_read_back() -> None:
    assert refusal_of([Decimal(1)], ["1.0"], None) is None


def test_data_that_reads_back_changed_is_refused_where_it_first_differs() -> None:
    refusal = refusal_of([1, (1, 2)], [1, [1, 2]], ANYTHING.validate_json)

    assert refusal is not None
    assert (refusal.path, refusal.error_type, refusal.current_type) == ("[1]", "not_exact", "tuple")


def test_a_value_reading_back_equal_as_another_type_is_refused() -> None:
    ints: TypeAdapter[dict[str, int]] = TypeAdapter(dict[str, int])

    refusal = refusal_of({"a": 1, "b": True}, {"a": 1, "b": 1}, ints.validate_json)

    assert refusal is not None
    assert (refusal.path, refusal.current_type) == ("b", "bool")


def test_a_set_member_reading_back_as_another_type_is_refused_at_the_set() -> None:
    ints: TypeAdapter[list[frozenset[int]]] = TypeAdapter(list[frozenset[int]])

    refusal = refusal_of([frozenset({True})], [[1]], ints.validate_json)

    assert refusal is not None
    assert (refusal.path, refusal.current_type) == ("[0]", "bool")


def test_a_datetime_subclass_may_read_back_as_a_datetime() -> None:
    datetimes: TypeAdapter[list[datetime]] = TypeAdapter(list[datetime])
    point = DatePoint(2026, 1, 1, tzinfo=UTC)

    assert refusal_of([point], ["2026-01-01T00:00:00Z"], datetimes.validate_json) is None


def test_written_data_with_no_json_form_is_refused_without_quoting_it() -> None:
    text = f"\ud800{PLANTED_VALUE}"

    refusal = refusal_of([text], [text], ANYTHING.validate_json)

    assert refusal is not None
    assert refusal.error_type == "not_json"
    assert PLANTED_VALUE not in "".join(traceback.format_exception(refusal))


def fail_to_read(_text: bytes) -> NoReturn:
    raise KeyError(PLANTED_VALUE)


def test_a_read_that_raises_is_refused_naming_only_what_it_raised() -> None:
    refusal = refusal_of([1], [1], fail_to_read)

    assert refusal is not None
    assert refusal.error_type == "not_read_back"
    assert "KeyError" in refusal.message
    assert PLANTED_VALUE not in refusal.message


def test_a_comparison_that_raises_is_refused_where_it_raised() -> None:
    def read_signalling_nan(_text: bytes) -> list[Decimal]:
        return [Decimal(1), Decimal("sNaN")]

    refusal = refusal_of([Decimal(1), Decimal("sNaN")], ["1", "sNaN"], read_signalling_nan)

    assert refusal is not None
    assert (refusal.path, refusal.error_type) == ("[1]", "not_comparable")


def fail_namelessly(_text: bytes) -> NoReturn:
    raise NamelessError


def test_a_read_raising_an_error_whose_metaclass_refuses_its_name_is_refused_naming_it() -> None:
    with names_refused():
        refusal = refusal_of([1], [1], fail_namelessly)

    assert refusal is not None
    assert "raised NamelessError" in refusal.message


def test_a_part_whose_metaclass_refuses_its_name_is_refused_naming_its_type() -> None:
    with names_refused():
        refusal = refusal_of([NamelessThing()], [{}], lambda _text: [NamelessThing()])

    assert refusal is not None
    assert (refusal.path, refusal.current_type) == ("[0]", "NamelessThing")


def test_deep_data_is_confirmed_however_little_of_the_stack_is_left() -> None:
    value: NormalizedValue = 0
    for _ in range(150):
        value = [value]

    def confirm_from(depth: int) -> NotNormalizableValueError | None:
        if depth:
            return confirm_from(depth - 1)
        return refusal_of(value, value, ANYTHING.validate_json)

    # Leaves a few dozen frames of the stack, far fewer than the data's depth.
    assert confirm_from(sys.getrecursionlimit() - len(inspect.stack(0)) - 50) is None
