"""Data pydantic refused to read becomes this package's error, located in what was read."""

from __future__ import annotations

from pydantic_core import ErrorDetails

from xtr_serializer.exception import NotNormalizableValueError, PartialDenormalizationError
from xtr_serializer.normalizer._read_refusal import read_refusal


def string_error_at(*loc: str | int) -> ErrorDetails:
    return ErrorDetails(type="string_type", loc=loc, msg="Input should be a valid string", input=1)


def test_the_first_refusal_is_given_located_in_the_json_read() -> None:
    refusal = read_refusal(
        object(), [string_error_at("a"), string_error_at("b")], b'{"a": 1, "b": 1}', collect=False
    )

    assert isinstance(refusal, NotNormalizableValueError)
    assert refusal.path == "a"


def test_every_refusal_is_given_when_collected() -> None:
    data = {"a": 1, "b": 1}

    refusal = read_refusal(data, [string_error_at("a"), string_error_at("b")], None, collect=True)

    assert isinstance(refusal, PartialDenormalizationError)
    assert [error.path for error in refusal.errors] == ["a", "b"]


def test_json_nested_past_parsing_is_located_nowhere() -> None:
    refusal = read_refusal([], [string_error_at(0)], b"[" * 10_000, collect=False)

    assert isinstance(refusal, NotNormalizableValueError)
    assert refusal.path is None


def test_no_error_from_pydantic_is_a_refusal_of_the_whole_data() -> None:
    refusal = read_refusal([], [], None, collect=False)

    assert isinstance(refusal, NotNormalizableValueError)
    assert (refusal.path, refusal.current_type) == (None, "list")
