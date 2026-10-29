"""What is handed the denormalizer for nested values is told by its setter."""

from __future__ import annotations

from tests.support.point_normalizer import PointNormalizer
from tests.support.segment_normalizer import SegmentNormalizer
from tests.support.shapes import Point, Segment
from xtr_serializer import DenormalizerAwareInterface


def test_a_denormalizer_handed_one_for_its_parts_satisfies_it() -> None:
    assert isinstance(SegmentNormalizer(), DenormalizerAwareInterface)


def test_a_denormalizer_with_no_parts_to_hand_on_does_not() -> None:
    assert not isinstance(PointNormalizer(), DenormalizerAwareInterface)


def test_the_denormalizer_handed_over_through_it_builds_the_parts() -> None:
    segments = SegmentNormalizer()
    aware: DenormalizerAwareInterface = segments

    aware.set_denormalizer(PointNormalizer())

    assert segments.denormalize(
        {"start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 4}},
        Segment,
    ) == Segment(Point(0, 0), Point(3, 4))
