"""The declared encoder keeps the encoder and decoder contracts, by declaration."""

from __future__ import annotations

from tests.support.declared_encoder import DeclaredEncoder
from tests.support.in_memory_encoder import MEMORY
from xtr_serializer import DecoderInterface, EncoderInterface


def test_it_subclasses_both_interfaces() -> None:
    assert EncoderInterface in DeclaredEncoder.__mro__
    assert DecoderInterface in DeclaredEncoder.__mro__


def test_it_reads_back_what_it_wrote() -> None:
    encoder = DeclaredEncoder()

    written = encoder.encode({"a": [1]}, MEMORY)

    assert encoder.decode(written, MEMORY) == {"a": [1]}


def test_it_handles_its_format_only() -> None:
    encoder = DeclaredEncoder()

    assert (encoder.supports_encoding(MEMORY), encoder.supports_decoding(MEMORY)) == (True, True)
    assert (encoder.supports_encoding("json"), encoder.supports_decoding("json")) == (False, False)
