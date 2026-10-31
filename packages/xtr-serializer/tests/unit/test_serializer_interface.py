"""A serializer is told by its two methods, and what it reads is typed by the type asked for."""

from __future__ import annotations

from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.point_normalizer import PointNormalizer
from tests.support.shapes import Point
from xtr_serializer import Serializer, SerializerInterface


def point_serializer() -> Serializer:
    return Serializer([PointNormalizer()], [InMemoryEncoder()])


def test_a_serializer_satisfies_it() -> None:
    assert isinstance(point_serializer(), SerializerInterface)


def test_an_encoder_does_not() -> None:
    assert not isinstance(InMemoryEncoder(), SerializerInterface)


def test_a_value_read_into_a_class_is_typed_as_an_instance_of_it() -> None:
    serializer: SerializerInterface = point_serializer()
    text = serializer.serialize(Point(1, 2), MEMORY)

    point: Point = serializer.deserialize(text, Point, MEMORY)

    assert point == Point(1, 2)


def test_a_type_held_only_as_an_object_can_be_read_into() -> None:
    serializer: SerializerInterface = point_serializer()
    text = serializer.serialize(Point(1, 2), MEMORY)

    assert _read_into(Point, serializer, text) == Point(1, 2)


def _read_into(type_: object, serializer: SerializerInterface, text: str) -> object:
    """Read ``text`` into a type known only when the program runs, as one named in a header."""
    return serializer.deserialize(text, type_, MEMORY)
