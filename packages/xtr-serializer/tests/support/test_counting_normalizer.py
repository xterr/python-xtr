"""The counting normalizer keeps the contracts it stands in for, and counts and records calls."""

from __future__ import annotations

from tests.support.counting_normalizer import CountingNormalizer
from tests.support.in_memory_encoder import MEMORY
from tests.support.shapes import Point
from xtr_serializer import DenormalizerInterface, NormalizerInterface


def test_it_is_a_normalizer_and_a_denormalizer() -> None:
    normalizer = CountingNormalizer("n", {})

    assert isinstance(normalizer, NormalizerInterface)
    assert isinstance(normalizer, DenormalizerInterface)


def test_it_writes_any_value_as_its_name() -> None:
    assert CountingNormalizer("n", {}).normalize(Point(1, 2)) == "n"


def test_it_reads_any_data_as_its_name() -> None:
    assert CountingNormalizer("n", {}).denormalize({"x": 1}, Point) == "n"


def test_it_records_the_context_and_type_of_each_call() -> None:
    normalizer = CountingNormalizer("n", {})

    _ = normalizer.normalize(Point(1, 2), MEMORY, {"a": 1}, type_=Point)
    _ = normalizer.denormalize({}, int, MEMORY, {"b": 2})

    assert normalizer.calls == [({"a": 1}, Point), ({"b": 2}, int)]


def test_it_counts_each_time_it_is_asked_whether_it_handles_a_value() -> None:
    normalizer = CountingNormalizer("n", {})

    _ = normalizer.supports_normalization(Point(1, 2))
    _ = normalizer.supports_denormalization({}, Point)

    assert normalizer.asked == 2


def test_it_answers_as_it_was_told_to() -> None:
    normalizer = CountingNormalizer("n", {}, handles=False)

    assert not normalizer.supports_normalization(Point(1, 2))
    assert not normalizer.supports_denormalization({}, Point)


def test_it_reports_the_types_it_was_given_for_a_format_and_none_in_another() -> None:
    normalizer = CountingNormalizer("n", {MEMORY: {Point: True}})

    assert (normalizer.get_supported_types(MEMORY), normalizer.get_supported_types("json")) == (
        {Point: True},
        {},
    )
