"""A denormalizer is told by its three methods, and what it builds is typed by what was asked."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.point_normalizer import PointNormalizer
from tests.support.shapes import Point
from xtr_serializer import COLLECT_DENORMALIZATION_ERRORS, DenormalizerInterface

if TYPE_CHECKING:
    from xtr_serializer import Context


@final
class _SilentAboutItsTypes:
    """Denormalizes, but never says which types it builds."""

    def denormalize(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> object:
        del type_, format, context
        return data

    def supports_denormalization(
        self,
        data: object,
        type_: object,
        format: str | None = None,
        context: Context | None = None,
    ) -> bool:
        del data, type_, format, context
        return True


def test_a_denormalizer_satisfies_it() -> None:
    assert isinstance(PointNormalizer(), DenormalizerInterface)


def test_one_that_does_not_say_which_types_it_builds_does_not() -> None:
    assert not isinstance(_SilentAboutItsTypes(), DenormalizerInterface)


def test_an_encoder_does_not() -> None:
    assert not isinstance(InMemoryEncoder(), DenormalizerInterface)


def test_a_value_built_as_a_class_is_typed_as_an_instance_of_it() -> None:
    denormalizer: DenormalizerInterface = PointNormalizer()

    point: Point = denormalizer.denormalize({"x": 1, "y": 2}, Point, MEMORY, {})

    assert point == Point(1, 2)


def test_a_type_held_only_as_an_object_can_be_built() -> None:
    assert _build(Point, PointNormalizer()) == Point(1, 2)


def _build(type_: object, denormalizer: DenormalizerInterface) -> object:
    """Build a type known only when the program runs, as one named in a header."""
    return denormalizer.denormalize({"x": 1, "y": 2}, type_)


def test_its_key_is_spelled_as_an_application_writes_it_in_a_context() -> None:
    assert COLLECT_DENORMALIZATION_ERRORS == "collect_denormalization_errors"
