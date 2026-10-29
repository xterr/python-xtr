"""What is handed the normalizer for nested values is told by its setter."""

from __future__ import annotations

from tests.support.point_normalizer import PointNormalizer
from tests.support.segment_normalizer import SegmentNormalizer
from tests.support.shapes import Point, Segment
from xtr_serializer import NormalizerAwareInterface


def test_a_normalizer_handed_one_for_its_parts_satisfies_it() -> None:
    assert isinstance(SegmentNormalizer(), NormalizerAwareInterface)


def test_a_normalizer_with_no_parts_to_hand_on_does_not() -> None:
    assert not isinstance(PointNormalizer(), NormalizerAwareInterface)


def test_the_normalizer_handed_over_through_it_writes_the_parts() -> None:
    segments = SegmentNormalizer()
    aware: NormalizerAwareInterface = segments

    aware.set_normalizer(PointNormalizer())

    assert segments.normalize(Segment(Point(0, 0), Point(3, 4))) == {
        "start": {"x": 0, "y": 0},
        "end": {"x": 3, "y": 4},
    }
