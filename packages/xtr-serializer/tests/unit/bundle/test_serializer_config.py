"""The bundle's configuration: a default context and the serializers named besides the default."""

from __future__ import annotations

from typing import cast

import pytest

from xtr_serializer.bundle import DEFAULT_SERIALIZER, NamedSerializerConfig, SerializerConfig
from xtr_serializer.exception import InvalidArgumentError


def test_it_builds_with_no_arguments_naming_no_other_serializer() -> None:
    config = SerializerConfig()

    assert (dict(config.default_context), dict(config.named_serializers)) == ({}, {})


def test_a_named_serializer_is_kept_under_its_name() -> None:
    api = NamedSerializerConfig(include_built_in_encoders=False)

    config = SerializerConfig(named_serializers={"api": api})

    assert config.named_serializers["api"] is api


def test_an_empty_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="non-empty name"):
        _ = SerializerConfig(named_serializers={"": NamedSerializerConfig()})


def test_a_name_that_is_not_a_string_is_refused() -> None:
    named = cast("dict[str, NamedSerializerConfig]", {1: NamedSerializerConfig()})

    with pytest.raises(InvalidArgumentError, match="non-empty name"):
        _ = SerializerConfig(named_serializers=named)


@pytest.mark.parametrize("name", [DEFAULT_SERIALIZER, "*"])
def test_the_default_name_and_the_wildcard_are_reserved(name: str) -> None:
    with pytest.raises(InvalidArgumentError, match="reserved"):
        _ = SerializerConfig(named_serializers={name: NamedSerializerConfig()})


def test_a_named_serializer_configured_with_something_else_is_refused() -> None:
    named = cast("dict[str, NamedSerializerConfig]", {"api": {"include_built_in_encoders": False}})

    with pytest.raises(InvalidArgumentError, match="NamedSerializerConfig"):
        _ = SerializerConfig(named_serializers=named)


def test_a_default_context_keyed_by_something_else_than_strings_is_refused() -> None:
    context = cast("dict[str, object]", {None: True})

    with pytest.raises(InvalidArgumentError, match="default context"):
        _ = SerializerConfig(default_context=context)


@pytest.mark.parametrize("named", [["api"], "api", None])
def test_named_serializers_that_are_no_mapping_are_refused(named: object) -> None:
    with pytest.raises(InvalidArgumentError, match="named_serializers"):
        _ = SerializerConfig(named_serializers=cast("dict[str, NamedSerializerConfig]", named))
