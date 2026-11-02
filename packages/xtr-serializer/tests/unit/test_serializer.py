"""A serializer hands each value to the first of its normalizers, and each text to its encoders."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, final

import pytest

from tests.support.counting_normalizer import CountingNormalizer
from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.parcel_normalizer import ParcelNormalizer
from tests.support.point_normalizer import PointNormalizer
from tests.support.segment_normalizer import SegmentNormalizer
from tests.support.shapes import Parcel, Point, Segment
from xtr_serializer import (
    DecoderInterface,
    DenormalizerInterface,
    EncoderInterface,
    NormalizerInterface,
    PydanticNormalizer,
    Serializer,
    SerializerInterface,
)
from xtr_serializer.exception import (
    InvalidArgumentError,
    NotNormalizableValueError,
    UnsupportedFormatError,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_serializer import Context, NormalizedValue, SupportedTypes

SEGMENT = Segment(Point(0, 0), Point(3, 4))
EVERYTHING: Mapping[str | None, SupportedTypes] = {MEMORY: {"*": False}, None: {"*": False}}


class Tone(StrEnum):
    """A member that is a string, and yet not plain data."""

    LOW = "low"


@final
class RecordingEncoder:
    """Writes plain data as its ``repr``, recording the context and the serializer it is handed."""

    def __init__(self) -> None:
        self.contexts: list[Context | None] = []
        self.serializer: SerializerInterface | None = None

    def set_serializer(self, serializer: SerializerInterface, /) -> None:
        self.serializer = serializer

    def encode(self, data: NormalizedValue, format: str, context: Context | None = None) -> str:
        del format
        self.contexts.append(context)
        return repr(data)

    def supports_encoding(self, format: str) -> bool:
        return format == MEMORY


def test_it_is_a_serializer_normalizer_denormalizer_encoder_and_decoder() -> None:
    serializer = Serializer()
    interfaces = (
        SerializerInterface,
        NormalizerInterface,
        DenormalizerInterface,
        EncoderInterface,
        DecoderInterface,
    )

    assert all(isinstance(serializer, interface) for interface in interfaces)


def test_it_refuses_a_normalizer_that_neither_normalizes_nor_denormalizes() -> None:
    with pytest.raises(InvalidArgumentError, match="'InMemoryEncoder'"):
        _ = Serializer([InMemoryEncoder()])  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type] - what is refused


def test_it_refuses_an_encoder_that_neither_encodes_nor_decodes() -> None:
    with pytest.raises(InvalidArgumentError, match="'PointNormalizer'"):
        _ = Serializer(encoders=[PointNormalizer()])  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type] - what is refused


def test_it_hands_itself_as_the_normalizer_of_nested_values() -> None:
    serializer = Serializer([SegmentNormalizer(), PointNormalizer()])

    assert serializer.normalize(SEGMENT) == {"start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 4}}


def test_it_hands_itself_as_the_denormalizer_of_nested_values() -> None:
    serializer = Serializer([SegmentNormalizer(), PointNormalizer()])
    data = {"start": {"x": 0, "y": 0}, "end": {"x": 3, "y": 4}}

    assert serializer.denormalize(data, Segment) == SEGMENT


def test_it_hands_itself_to_a_normalizer_that_needs_the_serializer() -> None:
    serializer = Serializer([ParcelNormalizer(MEMORY), PointNormalizer()], [InMemoryEncoder()])

    text = serializer.serialize(Parcel(Point(1, 2)), MEMORY)

    assert serializer.deserialize(text, Parcel, MEMORY) == Parcel(Point(1, 2))


def test_it_hands_itself_to_an_encoder_that_needs_the_serializer() -> None:
    encoder = RecordingEncoder()

    serializer = Serializer(encoders=[encoder])

    assert encoder.serializer is serializer


def test_the_first_normalizer_listed_that_handles_a_value_writes_it() -> None:
    first, second = (
        CountingNormalizer("first", EVERYTHING),
        CountingNormalizer("second", EVERYTHING),
    )

    assert Serializer([first, second]).normalize(Point(1, 2), MEMORY) == "first"


def test_a_normalizer_that_does_not_handle_a_value_is_passed_over() -> None:
    first = CountingNormalizer("first", EVERYTHING, handles=False)
    second = CountingNormalizer("second", EVERYTHING)

    assert Serializer([first, second]).normalize(Point(1, 2), MEMORY) == "second"


def test_the_first_denormalizer_listed_that_handles_a_type_reads_it() -> None:
    first = CountingNormalizer("first", EVERYTHING, handles=False)
    second = CountingNormalizer("second", EVERYTHING)

    assert Serializer([first, second]).denormalize({}, Point, MEMORY) == "second"


def test_the_call_context_wins_over_the_default_one() -> None:
    normalizer = CountingNormalizer("n", EVERYTHING)
    serializer = Serializer([normalizer], default_context={"a": 1, "b": 1})

    _ = serializer.normalize(Point(1, 2), MEMORY, {"b": 2})

    assert normalizer.calls == [({"a": 1, "b": 2}, None)]


def test_a_default_context_changed_after_the_serializer_is_built_is_not_picked_up() -> None:
    normalizer = CountingNormalizer("n", EVERYTHING)
    default: dict[str, object] = {"a": 1}
    serializer = Serializer([normalizer], default_context=default)
    default["a"] = 2

    _ = serializer.denormalize({}, Point, MEMORY)

    assert normalizer.calls == [({"a": 1}, Point)]


def test_serializing_hands_the_merged_context_to_each_step() -> None:
    normalizer, encoder = CountingNormalizer("n", EVERYTHING), RecordingEncoder()
    serializer = Serializer([normalizer], [encoder], default_context={"a": 1})

    _ = serializer.serialize(Point(1, 2), MEMORY, {"b": 2})

    assert (normalizer.calls, encoder.contexts) == ([({"a": 1, "b": 2}, None)], [{"a": 1, "b": 2}])


@pytest.mark.parametrize("value", [None, True, 7, 1.5, "text"])
def test_a_primitive_is_written_as_it_is_without_asking_a_normalizer(value: object) -> None:
    normalizer = CountingNormalizer("n", EVERYTHING)

    assert Serializer([normalizer]).normalize(value, MEMORY) == value
    assert normalizer.asked == 0


def test_a_member_that_is_a_string_is_handed_to_a_normalizer() -> None:
    assert Serializer([CountingNormalizer("n", EVERYTHING)]).normalize(Tone.LOW, MEMORY) == "n"


def test_a_primitive_with_a_declared_type_is_handed_to_a_normalizer() -> None:
    normalizer = CountingNormalizer("n", EVERYTHING)

    _ = Serializer([normalizer]).normalize(True, MEMORY, type_=int)

    assert normalizer.calls == [({}, int)]


def test_a_value_declared_as_a_type_the_normalizer_refuses_is_refused() -> None:
    with pytest.raises(NotNormalizableValueError):
        _ = Serializer([PydanticNormalizer()]).normalize(True, type_=int)


def test_a_value_no_normalizer_handles_is_refused_naming_its_class() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = Serializer([SegmentNormalizer()]).normalize(Point(1, 2))

    assert raised.value.current_type == "Point"


def test_a_type_no_denormalizer_reads_is_refused_naming_it() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = Serializer([SegmentNormalizer()]).denormalize({}, list[Point])

    assert raised.value.expected_types == ("list[Point]",)


def test_it_refuses_to_serialize_a_format_it_has_no_encoder_for_before_normalizing() -> None:
    normalizer = CountingNormalizer("n", EVERYTHING)

    with pytest.raises(UnsupportedFormatError):
        _ = Serializer([normalizer], [InMemoryEncoder()]).serialize(Point(1, 2), "json")
    assert (normalizer.asked, normalizer.calls) == (0, [])


def test_it_refuses_to_deserialize_a_format_it_has_no_decoder_for() -> None:
    with pytest.raises(UnsupportedFormatError):
        _ = Serializer([PointNormalizer()], [RecordingEncoder()]).deserialize("{}", Point, MEMORY)


def test_it_encodes_and_decodes_with_the_first_encoder_for_the_format() -> None:
    serializer = Serializer(encoders=[RecordingEncoder(), InMemoryEncoder()])

    text = serializer.encode({"a": 1}, MEMORY)

    assert (text, serializer.supports_decoding(MEMORY)) == ("{'a': 1}", True)


@pytest.mark.parametrize("step", ["encode", "decode"])
def test_it_refuses_to_encode_or_decode_a_format_it_has_none_for(step: str) -> None:
    serializer = Serializer(encoders=[InMemoryEncoder()])

    with pytest.raises(UnsupportedFormatError):
        _ = serializer.encode({}, "json") if step == "encode" else serializer.decode("{}", "json")


def test_it_tells_which_formats_it_writes_and_reads() -> None:
    serializer = Serializer(encoders=[RecordingEncoder()])

    assert (serializer.supports_encoding(MEMORY), serializer.supports_decoding(MEMORY)) == (
        True,
        False,
    )


def test_it_handles_primitives_and_what_one_of_its_normalizers_handles() -> None:
    serializer = Serializer([PointNormalizer()])

    assert [serializer.supports_normalization(value) for value in (1, Point(1, 2), SEGMENT)] == [
        True,
        True,
        False,
    ]


def test_it_reads_into_what_one_of_its_denormalizers_reads_into() -> None:
    serializer = Serializer([PointNormalizer()])

    assert [serializer.supports_denormalization({}, type_) for type_ in (Point, Segment)] == [
        True,
        False,
    ]


def test_its_answer_is_never_remembered_by_a_serializer_holding_it() -> None:
    assert Serializer().get_supported_types(None) == {"*": False}


def test_it_remembers_which_normalizer_handles_a_type_whose_answer_rests_on_it_alone() -> None:
    normalizer = CountingNormalizer("n", {None: {Point: True}})
    serializer = Serializer([normalizer])

    _ = [serializer.normalize(Point(index, index)) for index in range(3)]

    assert normalizer.asked == 1
