"""A serializer's factory takes each of its normalizers and encoders as a parameter, in order."""

from __future__ import annotations

import inspect
from typing import Annotated, get_type_hints

from xtr_dependency_injection import Target

from tests.support.counting_normalizer import CountingNormalizer
from tests.support.in_memory_encoder import MEMORY, InMemoryEncoder
from xtr_serializer import JsonEncoder, PydanticNormalizer, Serializer
from xtr_serializer.bundle._serializer_factory import serializer_factory


def test_it_takes_the_context_then_each_service_by_keyword() -> None:
    factory = serializer_factory(
        None,
        [(CountingNormalizer, "app"), (PydanticNormalizer, None)],
        [(JsonEncoder, None)],
    )

    parameters = inspect.signature(factory).parameters

    assert list(parameters) == ["default_context", "normalizer_0", "normalizer_1", "encoder_0"]
    assert {one.kind for one in parameters.values()} == {inspect.Parameter.KEYWORD_ONLY}


def test_a_qualified_service_is_targeted_and_an_unqualified_one_named_by_its_type() -> None:
    factory = serializer_factory(None, [(CountingNormalizer, "app")], [(JsonEncoder, None)])

    hints = get_type_hints(factory, include_extras=True)

    assert hints["normalizer_0"] == Annotated[CountingNormalizer, Target("app")]
    assert hints["encoder_0"] is JsonEncoder
    assert hints["return"] is Serializer


def test_it_is_named_after_its_serializer() -> None:
    default = serializer_factory(None, [], [])
    named = serializer_factory("api.v2", [], [])

    assert (getattr(default, "__name__", None), getattr(named, "__name__", None)) == (
        "serializer",
        "serializer_api_v2",
    )


def test_it_builds_a_serializer_of_the_services_in_order_with_the_context() -> None:
    factory = serializer_factory(
        None,
        [(CountingNormalizer, "first"), (CountingNormalizer, "second")],
        [(InMemoryEncoder, None)],
    )
    first = CountingNormalizer("first", {MEMORY: {"*": True}})
    second = CountingNormalizer("second", {MEMORY: {"*": True}})

    serializer = factory(
        default_context={"flag": 1},
        normalizer_0=first,
        normalizer_1=second,
        encoder_0=InMemoryEncoder(),
    )
    _ = serializer.normalize(object(), MEMORY)

    assert first.calls == [({"flag": 1}, None)]
    assert second.calls == []
