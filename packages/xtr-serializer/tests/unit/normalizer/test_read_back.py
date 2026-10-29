"""Written data read back and compared, so what would come back changed is refused."""

from __future__ import annotations

from decimal import Decimal

from pydantic import ConfigDict, TypeAdapter

from xtr_serializer.normalizer._read_back import read_back_refusal

DECIMALS: TypeAdapter[list[Decimal]] = TypeAdapter(list[Decimal])
ANYTHING: TypeAdapter[list[object]] = TypeAdapter(list[object])


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


def test_data_that_reads_back_changed_is_refused_without_a_place() -> None:
    refusal = read_back_refusal([(1, 2)], [[1, 2]], ANYTHING.validate_json)

    assert refusal is not None
    assert (refusal.path, refusal.error_type, refusal.current_type) == (None, "not_exact", "list")
