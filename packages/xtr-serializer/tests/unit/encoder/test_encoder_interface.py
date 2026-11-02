"""An encoder is told by writing plain data and by naming the formats it writes."""

from __future__ import annotations

from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.point_normalizer import PointNormalizer
from xtr_serializer import EncoderInterface


def test_an_encoder_satisfies_it() -> None:
    assert isinstance(InMemoryEncoder(), EncoderInterface)


def test_a_normalizer_does_not() -> None:
    assert not isinstance(PointNormalizer(), EncoderInterface)


def test_an_encoder_is_called_through_it() -> None:
    encoder: EncoderInterface = InMemoryEncoder()

    assert encoder.encode({"x": 1, "y": 2}, MEMORY, {}) == "#1"
