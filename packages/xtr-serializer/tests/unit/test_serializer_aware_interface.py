"""What is handed the serializer it belongs to is told by its setter."""

from __future__ import annotations

from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.parcel_normalizer import ParcelNormalizer
from tests.support.point_normalizer import PointNormalizer
from tests.support.shapes import Parcel, Point
from xtr_serializer import Serializer, SerializerAwareInterface


def test_a_normalizer_handed_a_serializer_satisfies_it() -> None:
    assert isinstance(ParcelNormalizer(MEMORY), SerializerAwareInterface)


def test_a_normalizer_that_needs_none_does_not() -> None:
    assert not isinstance(PointNormalizer(), SerializerAwareInterface)


def test_the_serializer_handed_over_through_it_is_the_one_used() -> None:
    parcels = ParcelNormalizer(MEMORY)
    aware: SerializerAwareInterface = parcels
    serializer = Serializer([PointNormalizer()], [InMemoryEncoder()])

    aware.set_serializer(serializer)

    assert parcels.normalize(Parcel(Point(1, 2))) == {"content": "#1"}
    assert serializer.deserialize("#1", Point, MEMORY) == Point(1, 2)
