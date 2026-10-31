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


@pytest.mark.parametrize("value", [1, "yes", None])
def test_include_built_in_normalizers_that_is_no_boolean_is_refused(value: object) -> None:
    with pytest.raises(InvalidArgumentError, match="include_built_in_normalizers"):
        _ = NamedSerializerConfig(include_built_in_normalizers=cast("bool", value))


@pytest.mark.parametrize("value", [0, "no", None])
def test_include_built_in_encoders_that_is_no_boolean_is_refused(value: object) -> None:
    with pytest.raises(InvalidArgumentError, match="include_built_in_encoders"):
        _ = NamedSerializerConfig(include_built_in_encoders=cast("bool", value))


def test_a_switch_that_is_no_boolean_is_refused_naming_its_type() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = NamedSerializerConfig(include_built_in_encoders=cast("bool", cast("object", 1)))

    assert str(raised.value).endswith("is True or False, not a value of type int")
