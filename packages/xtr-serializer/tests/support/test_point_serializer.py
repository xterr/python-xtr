"""The point serializer keeps the serializer contract it stands in for."""

from __future__ import annotations

import pytest

from tests.support.in_memory_encoder import MEMORY
from tests.support.point_serializer import PointSerializer
from tests.support.shapes import Point
from xtr_serializer import SerializerInterface
from xtr_serializer.exception import InvalidArgumentError, UnsupportedFormatError


def test_it_is_a_serializer() -> None:
    assert isinstance(PointSerializer(), SerializerInterface)


def test_a_point_it_wrote_reads_back_equal() -> None:
    serializer = PointSerializer()

    text = serializer.serialize(Point(1, 2), MEMORY)

    assert serializer.deserialize(text, Point, MEMORY) == Point(1, 2)


def test_it_refuses_to_write_a_format_it_has_no_encoder_for() -> None:
    with pytest.raises(UnsupportedFormatError):
        _ = PointSerializer().serialize(Point(1, 2), "json")


def test_it_refuses_to_read_a_format_it_has_no_decoder_for() -> None:
    with pytest.raises(UnsupportedFormatError):
        _ = PointSerializer().deserialize("{}", Point, "json")


def test_it_refuses_to_write_anything_but_a_point() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = PointSerializer().serialize((1, 2), MEMORY)
