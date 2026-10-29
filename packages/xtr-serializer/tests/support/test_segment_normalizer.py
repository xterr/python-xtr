"""The segment normalizer writes and reads its points through what it is handed."""

from __future__ import annotations

import pytest

from tests.support.point_normalizer import PointNormalizer
from tests.support.segment_normalizer import SegmentNormalizer
from tests.support.shapes import Point, Segment
from xtr_serializer import (
    DenormalizerAwareInterface,
    DenormalizerInterface,
    NormalizerAwareInterface,
    NormalizerInterface,
)
from xtr_serializer.exception import InvalidArgumentError, LogicError, NotNormalizableValueError

_SEGMENT = Segment(Point(0, 0), Point(3, 4))
_NORMALIZED = {"start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 4}}


def _handed_a_point_normalizer() -> SegmentNormalizer:
    normalizer = SegmentNormalizer()
    points = PointNormalizer()
    normalizer.set_normalizer(points)
    normalizer.set_denormalizer(points)
    return normalizer


def test_it_is_a_normalizer_and_a_denormalizer() -> None:
    normalizer = SegmentNormalizer()

    assert isinstance(normalizer, NormalizerInterface)
    assert isinstance(normalizer, DenormalizerInterface)


def test_it_is_handed_a_normalizer_and_a_denormalizer() -> None:
    normalizer = SegmentNormalizer()

    assert isinstance(normalizer, NormalizerAwareInterface)
    assert isinstance(normalizer, DenormalizerAwareInterface)


def test_it_writes_each_point_with_the_normalizer_it_was_handed() -> None:
    assert _handed_a_point_normalizer().normalize(_SEGMENT) == _NORMALIZED


def test_it_reads_each_point_with_the_denormalizer_it_was_handed() -> None:
    assert _handed_a_point_normalizer().denormalize(_NORMALIZED, Segment) == _SEGMENT


def test_writing_before_it_is_handed_a_normalizer_is_refused() -> None:
    with pytest.raises(LogicError):
        _ = SegmentNormalizer().normalize(_SEGMENT)


def test_reading_before_it_is_handed_a_denormalizer_is_refused() -> None:
    with pytest.raises(LogicError):
        _ = SegmentNormalizer().denormalize(_NORMALIZED, Segment)


def test_it_writes_segments_and_nothing_else() -> None:
    normalizer = SegmentNormalizer()

    assert normalizer.supports_normalization(_SEGMENT)
    assert not normalizer.supports_normalization(Point(0, 0))


def test_it_reads_into_segments_and_nothing_else() -> None:
    normalizer = SegmentNormalizer()

    assert normalizer.supports_denormalization(_NORMALIZED, Segment)
    assert not normalizer.supports_denormalization(_NORMALIZED, Point)


def test_its_answer_depends_on_the_type_alone() -> None:
    assert SegmentNormalizer().get_supported_types(None) == {Segment: True}


def test_it_refuses_to_write_anything_but_a_segment() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _handed_a_point_normalizer().normalize(Point(0, 0))


def test_it_refuses_to_read_into_anything_but_a_segment() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _handed_a_point_normalizer().denormalize(_NORMALIZED, Point)


def test_it_refuses_data_without_both_ends() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = _handed_a_point_normalizer().denormalize({"start": {"x": 0, "y": 0}}, Segment)

    assert (raised.value.expected_types, raised.value.current_type) == (("Segment",), "dict")
