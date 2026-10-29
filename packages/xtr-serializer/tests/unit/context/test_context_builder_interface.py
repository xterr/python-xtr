"""Every context builder is told by ``to_dict``, and is changed by nothing it takes or returns."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

import pytest

from xtr_serializer import (
    JSON_INDENT,
    ContextBuilderInterface,
    JsonEncoderContextBuilder,
    PydanticNormalizerContextBuilder,
    SerializerContextBuilder,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_serializer import Context

_Build: TypeAlias = "Callable[[Context | None], ContextBuilderInterface]"

_BUILDERS = [
    pytest.param(SerializerContextBuilder, id="serializer"),
    pytest.param(PydanticNormalizerContextBuilder, id="pydantic-normalizer"),
    pytest.param(JsonEncoderContextBuilder, id="json-encoder"),
]


@pytest.mark.parametrize("build", _BUILDERS)
def test_every_context_builder_satisfies_it(build: _Build) -> None:
    assert isinstance(build(None), ContextBuilderInterface)


def test_a_context_itself_does_not() -> None:
    assert not isinstance({JSON_INDENT: 2}, ContextBuilderInterface)


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
def test_a_change_to_the_dictionary_it_returned_does_not_reach_it(build: _Build) -> None:
    builder = build({JSON_INDENT: 2})
    context = builder.to_dict()

    context[JSON_INDENT] = 4

    assert builder.to_dict() == {JSON_INDENT: 2}
