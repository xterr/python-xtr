"""Every context builder starts from a copy and hands back a copy, so no caller can change it."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias, cast

import pytest

from xtr_serializer import (
    ATTRIBUTES,
    JSON_INDENT,
    JsonEncoderContextBuilder,
    PydanticNormalizerContextBuilder,
    SerializerContextBuilder,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_serializer import Context, ContextBuilderInterface

_Build: TypeAlias = "Callable[[Context | None], ContextBuilderInterface]"

_BUILDERS = [
    pytest.param(SerializerContextBuilder, id="serializer"),
    pytest.param(PydanticNormalizerContextBuilder, id="pydantic-normalizer"),
    pytest.param(JsonEncoderContextBuilder, id="json-encoder"),
]


@pytest.mark.parametrize("build", _BUILDERS)
def test_it_starts_with_no_options(build: _Build) -> None:
    assert build(None).to_dict() == {}


@pytest.mark.parametrize("build", _BUILDERS)
def test_it_starts_from_the_context_it_is_given(build: _Build) -> None:
    assert build({JSON_INDENT: 2}).to_dict() == {JSON_INDENT: 2}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_to_that_context_afterwards_does_not_reach_it(build: _Build) -> None:
    start: dict[str, object] = {JSON_INDENT: 2}
    builder = build(start)

    start[JSON_INDENT] = 4

    assert builder.to_dict() == {JSON_INDENT: 2}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_to_a_set_in_that_context_afterwards_does_not_reach_it(build: _Build) -> None:
    names = {"a"}
    builder = build({ATTRIBUTES: names})

    names.add("x")

    assert builder.to_dict() == {ATTRIBUTES: {"a"}}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_deep_inside_that_context_afterwards_does_not_reach_it(build: _Build) -> None:
    tags = ["a"]
    builder = build({"labels": {"tags": (tags,)}})

    tags.append("x")

    assert builder.to_dict() == {"labels": {"tags": (["a"],)}}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_to_the_dictionary_it_returned_does_not_reach_it(build: _Build) -> None:
    builder = build({JSON_INDENT: 2})
    context = builder.to_dict()

    context[JSON_INDENT] = 4

    assert builder.to_dict() == {JSON_INDENT: 2}


@pytest.mark.parametrize("build", _BUILDERS)
def test_a_change_to_a_set_it_returned_does_not_reach_it(build: _Build) -> None:
    builder = build({ATTRIBUTES: {"a"}})
    names = cast("set[str]", builder.to_dict()[ATTRIBUTES])

    names.add("x")

    assert builder.to_dict() == {ATTRIBUTES: {"a"}}


@pytest.mark.parametrize("build", _BUILDERS)
def test_an_object_in_that_context_is_handed_on_as_it_is(build: _Build) -> None:
    repository = object()

    handed_on = build({"repository": repository}).to_dict()["repository"]

    assert handed_on is repository
