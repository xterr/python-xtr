"""The parcel normalizer writes and reads its content through the serializer it is handed."""

from __future__ import annotations

import pytest

from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.parcel_normalizer import ParcelNormalizer
from tests.support.point_normalizer import PointNormalizer
from tests.support.shapes import Parcel, Point
from xtr_serializer import (
    DenormalizerInterface,
    NormalizerInterface,
    Serializer,
    SerializerAwareInterface,
)
from xtr_serializer.exception import InvalidArgumentError, LogicError, NotNormalizableValueError


def _handed_a_point_serializer() -> ParcelNormalizer:
    normalizer = ParcelNormalizer(MEMORY)
    normalizer.set_serializer(Serializer([PointNormalizer()], [InMemoryEncoder()]))
    return normalizer


def test_it_is_a_normalizer_and_a_denormalizer() -> None:
    normalizer = ParcelNormalizer(MEMORY)

    assert isinstance(normalizer, NormalizerInterface)
    assert isinstance(normalizer, DenormalizerInterface)


def test_it_is_handed_a_serializer() -> None:
    assert isinstance(ParcelNormalizer(MEMORY), SerializerAwareInterface)


def test_it_writes_the_content_as_the_text_its_serializer_wrote() -> None:
    assert _handed_a_point_serializer().normalize(Parcel(Point(1, 2))) == {"content": "#1"}


def test_it_reads_the_content_back_through_its_serializer() -> None:
    normalizer = _handed_a_point_serializer()
    normalized = normalizer.normalize(Parcel(Point(1, 2)))

    assert normalizer.denormalize(normalized, Parcel) == Parcel(Point(1, 2))


def test_writing_before_it_is_handed_a_serializer_is_refused() -> None:
    with pytest.raises(LogicError):
        _ = ParcelNormalizer(MEMORY).normalize(Parcel(Point(1, 2)))


def test_reading_before_it_is_handed_a_serializer_is_refused() -> None:
    with pytest.raises(LogicError):
        _ = ParcelNormalizer(MEMORY).denormalize({"content": "#1"}, Parcel)


def test_it_writes_parcels_and_nothing_else() -> None:
    normalizer = ParcelNormalizer(MEMORY)

    assert normalizer.supports_normalization(Parcel(Point(1, 2)))
    assert not normalizer.supports_normalization(Point(1, 2))


def test_it_reads_into_parcels_and_nothing_else() -> None:
    normalizer = ParcelNormalizer(MEMORY)

    assert normalizer.supports_denormalization({"content": "#1"}, Parcel)
    assert not normalizer.supports_denormalization({"content": "#1"}, Point)


def test_its_answer_depends_on_the_type_alone() -> None:
    assert ParcelNormalizer(MEMORY).get_supported_types(None) == {Parcel: True}


def test_it_refuses_to_write_anything_but_a_parcel() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _handed_a_point_serializer().normalize(Point(1, 2))


def test_it_refuses_to_read_into_anything_but_a_parcel() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = _handed_a_point_serializer().denormalize({"content": "#1"}, Point)


def test_it_refuses_data_without_text_content() -> None:
    with pytest.raises(NotNormalizableValueError) as raised:
        _ = _handed_a_point_serializer().denormalize({"content": 1}, Parcel)

    assert (raised.value.expected_types, raised.value.current_type) == (("Parcel",), "dict")
