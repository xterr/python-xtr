"""The declared normalizer keeps the normalizer and denormalizer contracts, by declaration."""

from __future__ import annotations

from tests.support.declared_normalizer import DECLARED, DeclaredNormalizer
from xtr_serializer import DenormalizerInterface, NormalizerInterface


def test_it_subclasses_both_interfaces() -> None:
    assert NormalizerInterface in DeclaredNormalizer.__mro__
    assert DenormalizerInterface in DeclaredNormalizer.__mro__


def test_it_writes_every_value_as_its_name() -> None:
    normalizer = DeclaredNormalizer()

    assert normalizer.supports_normalization(object())
    assert normalizer.normalize(object()) == DECLARED


def test_it_reads_any_data_back_as_its_name() -> None:
    normalizer = DeclaredNormalizer()

    assert normalizer.supports_denormalization({}, int)
    assert normalizer.denormalize({}, int) == DECLARED


def test_it_reports_every_type_whatever_the_value() -> None:
    assert DeclaredNormalizer().get_supported_types(None) == {"*": True}
