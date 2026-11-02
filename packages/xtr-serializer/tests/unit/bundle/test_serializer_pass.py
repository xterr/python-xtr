"""Each serializer is handed the normalizers and encoders tagged for it, highest priority first."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from tests.support.application_bundle import Registration, serializer_kernel
from tests.support.counting_normalizer import CountingNormalizer
from tests.support.declared_encoder import DeclaredEncoder
from tests.support.declared_normalizer import DECLARED, DeclaredNormalizer
from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from tests.support.point_normalizer import PointNormalizer
from tests.support.segment_normalizer import SegmentNormalizer
from tests.support.shapes import Point, Segment
from tests.support.shouting_normalizer import ShoutingNormalizer
from xtr_serializer import Serializer
from xtr_serializer.bundle import (
    ENCODER_TAG,
    NORMALIZER_TAG,
    NamedSerializerConfig,
    SerializerConfig,
)
from xtr_serializer.exception import LogicError, NotNormalizableValueError, UnsupportedFormatError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_dependency_injection import Kernel

    from xtr_serializer import NormalizedValue, SupportedTypes

pytestmark = pytest.mark.anyio

POINT = Point(1, 2)
EVERYTHING: Mapping[str | None, SupportedTypes] = {"json": {"*": False}, None: {"*": False}}
API = SerializerConfig(named_serializers={"api": NamedSerializerConfig()})


def _normalizer(name: str, **attributes: object) -> Registration:
    """Register a normalizer writing every value as ``name``, tagged with ``attributes``."""
    return Registration(CountingNormalizer(name, EVERYTHING), name, NORMALIZER_TAG, attributes)


async def _serializers(kernel: Kernel, *names: str | None) -> list[Serializer]:
    async with await kernel.boot() as booted:
        return [await booted.container.get(Serializer, name) for name in names]


async def _written(kernel: Kernel, value: object, name: str | None = None) -> NormalizedValue:
    [serializer] = await _serializers(kernel, name)
    return serializer.decode(serializer.serialize(value, "json"), "json")


async def test_an_application_normalizer_runs_before_the_built_in_one() -> None:
    kernel = serializer_kernel(None, _normalizer("app", priority=10))

    assert await _written(kernel, POINT) == "app"


async def test_the_highest_priority_runs_first() -> None:
    kernel = serializer_kernel(
        None, _normalizer("five", priority=5), _normalizer("ten", priority=10)
    )

    assert await _written(kernel, POINT) == "ten"


async def test_equal_priorities_run_in_the_order_they_were_registered() -> None:
    kernel = serializer_kernel(None, _normalizer("first"), _normalizer("second"))

    assert await _written(kernel, POINT) == "first"


async def test_a_tag_without_priority_takes_the_definition_priority() -> None:
    late = Registration(CountingNormalizer("late", EVERYTHING), "late", NORMALIZER_TAG)
    early = Registration(CountingNormalizer("early", EVERYTHING), "early", NORMALIZER_TAG, {}, 3)
    kernel = serializer_kernel(None, late, early)

    assert await _written(kernel, POINT) == "early"


async def test_a_normalizer_tagged_without_a_serializer_joins_the_default_one_only() -> None:
    kernel = serializer_kernel(API, _normalizer("app", priority=10))

    default, api = await _serializers(kernel, None, "api")

    assert json.loads(default.serialize(POINT, "json")) == "app"
    assert json.loads(api.serialize(POINT, "json")) == {"x": 1, "y": 2}


async def test_a_normalizer_tagged_for_a_named_serializer_joins_that_one_only() -> None:
    kernel = serializer_kernel(API, _normalizer("api-only", priority=10, serializer="api"))

    default, api = await _serializers(kernel, None, "api")

    assert json.loads(default.serialize(POINT, "json")) == {"x": 1, "y": 2}
    assert json.loads(api.serialize(POINT, "json")) == "api-only"


async def test_a_normalizer_tagged_for_several_serializers_joins_each() -> None:
    config = SerializerConfig(
        named_serializers={"api": NamedSerializerConfig(), "admin": NamedSerializerConfig()}
    )
    kernel = serializer_kernel(config, _normalizer("app", priority=10, serializer=["api", "admin"]))

    default, api, admin = await _serializers(kernel, None, "api", "admin")

    written = [json.loads(one.serialize(POINT, "json")) for one in (default, api, admin)]
    assert written == [{"x": 1, "y": 2}, "app", "app"]


async def test_a_normalizer_tagged_for_every_serializer_joins_each() -> None:
    kernel = serializer_kernel(API, _normalizer("app", priority=10, serializer="*"))

    default, api = await _serializers(kernel, None, "api")

    assert [json.loads(one.serialize(POINT, "json")) for one in (default, api)] == ["app", "app"]


async def test_each_serializer_hands_itself_to_its_own_copy_of_a_shared_normalizer() -> None:
    segment = Registration(SegmentNormalizer, None, NORMALIZER_TAG, {"serializer": "*"})
    points = Registration(
        CountingNormalizer("api-point", {"json": {Point: True}}),
        "api-point",
        NORMALIZER_TAG,
        {"serializer": "api"},
    )
    kernel = serializer_kernel(API, segment, points)

    default, api = await _serializers(kernel, None, "api")

    value = Segment(Point(0, 0), Point(1, 1))
    assert json.loads(default.serialize(value, "json"))["end"] == {"x": 1, "y": 1}
    assert json.loads(api.serialize(value, "json"))["end"] == "api-point"


async def test_a_named_serializer_can_leave_the_built_in_normalizers_out() -> None:
    config = SerializerConfig(
        named_serializers={"api": NamedSerializerConfig(include_built_in_normalizers=False)}
    )
    point = Registration(PointNormalizer(), None, NORMALIZER_TAG, {"serializer": "api"})
    kernel = serializer_kernel(config, point)

    [api] = await _serializers(kernel, "api")

    assert json.loads(api.serialize(POINT, "json")) == {"x": 1, "y": 2}
    with pytest.raises(NotNormalizableValueError):
        _ = api.serialize(Segment(POINT, POINT), "json")


async def test_a_named_serializer_left_without_a_normalizer_fails_the_build() -> None:
    config = SerializerConfig(
        named_serializers={"api": NamedSerializerConfig(include_built_in_normalizers=False)}
    )

    with pytest.raises(LogicError, match="'api' has no normalizer"):
        _ = serializer_kernel(config).build()


async def test_a_named_serializer_can_leave_the_built_in_encoders_out() -> None:
    config = SerializerConfig(
        named_serializers={"api": NamedSerializerConfig(include_built_in_encoders=False)}
    )
    memory = Registration(InMemoryEncoder(), None, ENCODER_TAG, {"serializer": "api"})
    kernel = serializer_kernel(config, memory)

    [api] = await _serializers(kernel, "api")

    assert api.deserialize(api.serialize(POINT, MEMORY), Point, MEMORY) == POINT
    with pytest.raises(UnsupportedFormatError):
        _ = api.serialize(POINT, "json")


async def test_a_named_serializer_left_without_an_encoder_fails_the_build() -> None:
    config = SerializerConfig(
        named_serializers={"api": NamedSerializerConfig(include_built_in_encoders=False)}
    )

    with pytest.raises(LogicError, match="'api' has no encoder"):
        _ = serializer_kernel(config).build()


async def test_a_class_declaring_the_normalizer_interfaces_is_tagged_without_being_told() -> None:
    kernel = serializer_kernel(None, Registration(DeclaredNormalizer))

    assert await _written(kernel, POINT) == DECLARED


async def test_a_class_declaring_the_encoder_interfaces_is_tagged_without_being_told() -> None:
    kernel = serializer_kernel(None, Registration(DeclaredEncoder))

    [serializer] = await _serializers(kernel, None)

    assert serializer.deserialize(serializer.serialize(POINT, MEMORY), Point, MEMORY) == POINT


async def test_the_contexts_merge_global_then_named_then_the_call() -> None:
    counting = CountingNormalizer("app", EVERYTHING)
    config = SerializerConfig(
        default_context={"a": "global", "b": "global", "c": "global"},
        named_serializers={
            "api": NamedSerializerConfig(default_context={"b": "named", "c": "named"})
        },
    )
    tagged = Registration(counting, None, NORMALIZER_TAG, {"serializer": "*", "priority": 1})
    kernel = serializer_kernel(config, tagged)

    default, api = await _serializers(kernel, None, "api")
    _ = default.normalize(POINT)
    _ = api.normalize(POINT, context={"c": "call"})

    assert [context for context, _type in counting.calls] == [
        {"a": "global", "b": "global", "c": "global"},
        {"a": "global", "b": "named", "c": "call"},
    ]


async def test_a_tag_naming_a_serializer_that_does_not_exist_fails_the_build() -> None:
    kernel = serializer_kernel(None, _normalizer("app", serializer="nowhere"))

    with pytest.raises(LogicError, match="'nowhere'"):
        _ = kernel.build()


@pytest.mark.parametrize(
    "attributes",
    [
        {"priority": "high"},
        {"priority": True},
        {"serializer": 3},
        {"serializer": ["default", 3]},
        {"serializer": []},
        {"built_in": "yes"},
    ],
)
async def test_a_tag_attribute_of_the_wrong_kind_fails_the_build(
    attributes: dict[str, object],
) -> None:
    kernel = serializer_kernel(None, _normalizer("app", **attributes))

    with pytest.raises(LogicError, match="CountingNormalizer"):
        _ = kernel.build()


async def test_a_tag_naming_no_serializer_fails_the_build() -> None:
    kernel = serializer_kernel(None, _normalizer("app", serializer=[]))

    with pytest.raises(LogicError, match="names no serializer"):
        _ = kernel.build()


async def test_a_decorated_normalizer_joins_once_decorated() -> None:
    declared = Registration(DeclaredNormalizer, priority=10)
    shouting = Registration(ShoutingNormalizer, decorates=DeclaredNormalizer)
    kernel = serializer_kernel(None, declared, shouting)

    assert await _written(kernel, POINT) == DECLARED.upper()


async def test_an_object_handed_its_serializer_joining_two_serializers_fails_the_build() -> None:
    segment = Registration(SegmentNormalizer(), None, NORMALIZER_TAG, {"serializer": "*"})
    kernel = serializer_kernel(API, segment)

    with pytest.raises(LogicError, match=r"SegmentNormalizer.*register it as a class"):
        _ = kernel.build()


async def test_an_object_handed_its_serializer_joining_one_serializer_is_kept() -> None:
    segment = Registration(SegmentNormalizer(), None, NORMALIZER_TAG, {"serializer": "api"})
    kernel = serializer_kernel(API, segment)

    [api] = await _serializers(kernel, "api")

    assert json.loads(api.serialize(Segment(POINT, POINT), "json"))["end"] == {"x": 1, "y": 2}


async def test_the_serializers_are_listed_under_neither_tag() -> None:
    report = serializer_kernel(API).build().report

    tags = {
        definition.key: definition.tags
        for definition in report.definitions
        if definition.key[0] is Serializer
    }

    assert set(tags) == {(Serializer, None), (Serializer, "api")}
    assert all(NORMALIZER_TAG not in one and ENCODER_TAG not in one for one in tags.values())
