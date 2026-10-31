"""An encoder chain hands each format to the first of its encoders, or decoders, handling it."""

from __future__ import annotations

import pytest

from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.point_normalizer import PointNormalizer
from xtr_serializer import InvalidArgumentError, JsonEncoder, UnsupportedFormatError
from xtr_serializer.encoder._encoder_chain import EncoderChain


def test_it_refuses_what_neither_encodes_nor_decodes() -> None:
    with pytest.raises(InvalidArgumentError, match="'PointNormalizer' neither encodes nor decodes"):
        _ = EncoderChain([PointNormalizer()])  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type] - what is refused


def test_the_first_encoder_and_decoder_listed_for_a_format_are_given() -> None:
    first, second = InMemoryEncoder(), InMemoryEncoder()
    chain = EncoderChain([first, second])

    assert (chain.encoder_for(MEMORY), chain.decoder_for(MEMORY)) == (first, first)


def test_the_encoder_for_another_format_is_passed_over() -> None:
    json = JsonEncoder()

    assert EncoderChain([InMemoryEncoder(), json]).encoder_for("json") is json


@pytest.mark.parametrize("step", ["encoder", "decoder"])
def test_a_format_none_handles_is_refused(step: str) -> None:
    chain = EncoderChain([InMemoryEncoder()])

    with pytest.raises(UnsupportedFormatError):
        _ = chain.encoder_for("json") if step == "encoder" else chain.decoder_for("json")


def test_it_tells_which_formats_it_writes_and_reads() -> None:
    chain = EncoderChain([InMemoryEncoder()])

    assert (chain.encodes(MEMORY), chain.decodes(MEMORY), chain.encodes("json")) == (
        True,
        True,
        False,
    )
