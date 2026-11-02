"""The pydantic normalizer's context builder sets each option under its own key, and no other."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

import pytest

from xtr_serializer import (
    ALLOW_EXTRA_ATTRIBUTES,
    ATTRIBUTES,
    BY_ALIAS,
    COLLECT_DENORMALIZATION_ERRORS,
    FROM_ATTRIBUTES,
    IGNORED_ATTRIBUTES,
    JSON_INDENT,
    POPULATE_BY_NAME,
    SKIP_DEFAULT_VALUES,
    SKIP_NULL_VALUES,
    SKIP_UNSET_VALUES,
    STRICT,
    PydanticNormalizerContextBuilder,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_serializer import Context

_Setting: TypeAlias = (
    "Callable[[PydanticNormalizerContextBuilder], PydanticNormalizerContextBuilder]"
)

_START: Context = {JSON_INDENT: 2, COLLECT_DENORMALIZATION_ERRORS: True}

_SETTINGS: list[tuple[_Setting, str, object]] = [
    (
        lambda builder: builder.with_attributes({"id", "name"}),
        ATTRIBUTES,
        frozenset({"id", "name"}),
    ),
    (
        lambda builder: builder.with_ignored_attributes({"password"}),
        IGNORED_ATTRIBUTES,
        frozenset({"password"}),
    ),
    (lambda builder: builder.with_skip_null_values(True), SKIP_NULL_VALUES, True),
    (lambda builder: builder.with_skip_unset_values(True), SKIP_UNSET_VALUES, True),
    (lambda builder: builder.with_skip_default_values(True), SKIP_DEFAULT_VALUES, True),
    (lambda builder: builder.with_by_alias(False), BY_ALIAS, False),
    (lambda builder: builder.with_strict(True), STRICT, True),
    (lambda builder: builder.with_allow_extra_attributes(False), ALLOW_EXTRA_ATTRIBUTES, False),
    (lambda builder: builder.with_from_attributes(True), FROM_ATTRIBUTES, True),
    (lambda builder: builder.with_populate_by_name(True), POPULATE_BY_NAME, True),
]


@pytest.mark.parametrize(
    ("setting", "key", "value"),
    _SETTINGS,
    ids=[key for _, key, _ in _SETTINGS],
)
def test_each_option_sets_its_own_key_and_no_other(
    setting: _Setting, key: str, value: object
) -> None:
    builder = setting(PydanticNormalizerContextBuilder(_START))

    assert builder.to_dict() == {**_START, key: value}


def test_the_fields_to_write_stay_those_named_when_the_set_given_changes() -> None:
    names = {"id"}
    builder = PydanticNormalizerContextBuilder().with_attributes(names)

    names.add("password")

    assert builder.to_dict() == {ATTRIBUTES: frozenset({"id"})}


def test_the_fields_never_written_stay_those_named_when_the_set_given_changes() -> None:
    names = {"password"}
    builder = PydanticNormalizerContextBuilder().with_ignored_attributes(names)

    names.add("id")

    assert builder.to_dict() == {IGNORED_ATTRIBUTES: frozenset({"password"})}


def test_setting_an_option_leaves_the_builder_it_was_set_on_as_it_was() -> None:
    builder = PydanticNormalizerContextBuilder(_START)

    _ = builder.with_strict(True)

    assert builder.to_dict() == _START


def test_setting_an_option_again_replaces_its_value() -> None:
    builder = PydanticNormalizerContextBuilder().with_strict(True)

    builder = builder.with_strict(False)

    assert builder.to_dict() == {STRICT: False}


def test_the_context_it_built_starts_an_equal_builder() -> None:
    built = (
        PydanticNormalizerContextBuilder(_START)
        .with_attributes({"id"})
        .with_skip_null_values(True)
        .with_strict(True)
        .to_dict()
    )

    assert PydanticNormalizerContextBuilder(built).to_dict() == built
