"""The point normalizer keeps the normalizer and denormalizer contracts it stands in for."""

from __future__ import annotations

import pytest

from tests.support.point_normalizer import PointNormalizer
from tests.support.shapes import Point, Segment
from xtr_serializer import DenormalizerInterface, NormalizerInterface
from xtr_serializer.exception import InvalidArgumentError, NotNormalizableValueError


def test_it_is_a_normalizer_and_a_denormalizer() -> None:
    normalizer = PointNormalizer()

    assert isinstance(normalizer, NormalizerInterface)
    assert isinstance(normalizer, DenormalizerInterface)


def test_it_writes_a_point_as_its_coordinates() -> None:
    assert PointNormalizer().normalize(Point(1, 2)) == {"x": 1, "y": 2}


def test_it_reads_coordinates_back_into_the_point() -> None:
    assert PointNormalizer().denormalize({"x": 1, "y": 2}, Point) == Point(1, 2)


def test_it_writes_points_and_nothing_else() -> None:
    normalizer = PointNormalizer()

    assert normalizer.supports_normalization(Point(1, 2))
    assert not normalizer.supports_normalization(Segment(Point(0, 0), Point(1, 1)))


def test_it_reads_into_points_and_nothing_else() -> None:
    normalizer = PointNormalizer()

    assert normalizer.supports_denormalization({"x": 1, "y": 2}, Point)
    assert not normalizer.supports_denormalization({"x": 1, "y": 2}, Segment)


def test_its_answer_depends_on_the_type_alone() -> None:
    assert PointNormalizer().get_supported_types(None) == {Point: True}


def test_it_refuses_to_write_anything_but_a_point() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = PointNormalizer().normalize((1, 2))


def test_it_refuses_to_read_into_anything_but_a_point() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = PointNormalizer().denormalize({"x": 1, "y": 2}, Segment)


def test_it_refuses_data_without_integer_coordinates() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = PointNormalizer().denormalize({"x": "1", "y": 2}, Point)

    assert (raised.value.expected_types, raised.value.current_type) == (("Point",), "dict")
