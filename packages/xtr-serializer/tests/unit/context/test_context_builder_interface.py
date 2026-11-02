"""Every context builder is told by ``to_dict``; a context itself is not one."""

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
