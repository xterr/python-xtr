"""A decoder is told by reading text back and by naming the formats it reads."""

from __future__ import annotations

from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.point_normalizer import PointNormalizer
from xtr_serializer import DecoderInterface


def test_a_decoder_satisfies_it() -> None:
    assert isinstance(InMemoryEncoder(), DecoderInterface)


def test_a_normalizer_does_not() -> None:
    assert not isinstance(PointNormalizer(), DecoderInterface)


def test_a_decoder_is_called_through_it() -> None:
    encoder = InMemoryEncoder()
    reference = encoder.encode({"x": 1, "y": 2}, MEMORY)
    decoder: DecoderInterface = encoder

    assert decoder.decode(reference, MEMORY, {}) == {"x": 1, "y": 2}
