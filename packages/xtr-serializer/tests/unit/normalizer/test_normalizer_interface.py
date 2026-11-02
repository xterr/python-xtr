"""A normalizer is told by its three methods, the types it handles among them."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.point_normalizer import PointNormalizer
from tests.support.shapes import Point
from xtr_serializer import NormalizerInterface

if TYPE_CHECKING:
    from xtr_serializer import Context, NormalizedValue


@final
class _SilentAboutItsTypes:
    """Normalizes, but never says which types it handles."""

    def normalize(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> NormalizedValue:
        del format, context
        return repr(data)

    def supports_normalization(
        self,
        data: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        del data, format, context
        return True


def test_a_normalizer_satisfies_it() -> None:
    assert isinstance(PointNormalizer(), NormalizerInterface)


def test_one_that_does_not_say_which_types_it_handles_does_not() -> None:
    assert not isinstance(_SilentAboutItsTypes(), NormalizerInterface)


def test_an_encoder_does_not() -> None:
    assert not isinstance(InMemoryEncoder(), NormalizerInterface)


def test_a_normalizer_is_called_through_it() -> None:
    normalizer: NormalizerInterface = PointNormalizer()

    assert normalizer.normalize(Point(1, 2), MEMORY, {}) == {"x": 1, "y": 2}
