"""A named serializer's configuration: its own default context and the built-ins it keeps."""

from __future__ import annotations

from typing import cast

import pytest

from xtr_serializer.bundle import NamedSerializerConfig
from xtr_serializer.exception import InvalidArgumentError


def test_it_builds_with_no_arguments_keeping_every_built_in() -> None:
    config = NamedSerializerConfig()

    assert dict(config.default_context) == {}
    assert (config.include_built_in_normalizers, config.include_built_in_encoders) == (True, True)


def test_a_default_context_keyed_by_something_else_than_strings_is_refused() -> None:
    context = cast("dict[str, object]", {("strict",): True})

    with pytest.raises(InvalidArgumentError, match="named serializer"):
        _ = NamedSerializerConfig(default_context=context)
