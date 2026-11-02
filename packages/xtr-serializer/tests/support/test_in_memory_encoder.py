"""The in-memory encoder keeps the encoder and decoder contracts it stands in for."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from xtr_serializer import DecoderInterface, EncoderInterface
from xtr_serializer.exception import NotEncodableValueError

if TYPE_CHECKING:
    from xtr_serializer import NormalizedValue


def test_it_is_an_encoder_and_a_decoder() -> None:
    encoder = InMemoryEncoder()

    assert isinstance(encoder, EncoderInterface)
    assert isinstance(encoder, DecoderInterface)


def test_it_writes_each_value_as_the_next_reference() -> None:
    encoder = InMemoryEncoder()

    references = [encoder.encode({"a": 1}, MEMORY), encoder.encode([1, 2], MEMORY)]

    assert references == ["#1", "#2"]


def test_it_reads_a_reference_back_into_an_equal_value() -> None:
    encoder = InMemoryEncoder()
    value: NormalizedValue = {
        "lines": [{"sku": "A-1", "quantity": 2, "price": 9.5, "gift": False}],
        "note": None,
    }

    assert encoder.decode(encoder.encode(value, MEMORY), MEMORY) == value


def test_a_value_changed_after_it_was_written_reads_back_as_it_was_written() -> None:
    encoder = InMemoryEncoder()
    tags: list[NormalizedValue] = ["a"]
    reference = encoder.encode({"tags": tags}, MEMORY)

    tags.append("b")

    assert encoder.decode(reference, MEMORY) == {"tags": ["a"]}


def test_it_reads_bytes_as_the_text_they_hold() -> None:
    encoder = InMemoryEncoder()
    reference = encoder.encode("hello", MEMORY)

    assert encoder.decode(reference.encode(), MEMORY) == "hello"


def test_it_refuses_text_it_did_not_write() -> None:
    with pytest.raises(NotEncodableValueError):
        _ = InMemoryEncoder().decode("#1", MEMORY)


def test_it_writes_and_reads_its_own_format() -> None:
    encoder = InMemoryEncoder()

    assert encoder.supports_encoding(MEMORY)
    assert encoder.supports_decoding(MEMORY)


def test_it_writes_and_reads_no_other_format() -> None:
    encoder = InMemoryEncoder()

    assert not encoder.supports_encoding("json")
    assert not encoder.supports_decoding("json")
