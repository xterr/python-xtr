"""The shouting normalizer writes what the declared one writes, in capitals."""

from __future__ import annotations

from tests.support.declared_normalizer import DECLARED, DeclaredNormalizer
from tests.support.shouting_normalizer import ShoutingNormalizer
from xtr_serializer import NormalizerInterface


def test_it_subclasses_the_normalizer_interface() -> None:
    assert NormalizerInterface in ShoutingNormalizer.__mro__


def test_it_writes_what_it_decorates_in_capitals() -> None:
    normalizer = ShoutingNormalizer(DeclaredNormalizer())

    assert normalizer.supports_normalization(object())
    assert normalizer.normalize(object()) == DECLARED.upper()
