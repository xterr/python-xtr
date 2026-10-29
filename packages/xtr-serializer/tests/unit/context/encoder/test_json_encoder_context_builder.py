"""The JSON encoder's context builder sets each option under its own key, and no other."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypeAlias

import pytest

from xtr_serializer import (
    COLLECT_DENORMALIZATION_ERRORS,
    JSON_INDENT,
    STRICT,
    JsonEncoderContextBuilder,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_serializer import Context

_Setting: TypeAlias = "Callable[[JsonEncoderContextBuilder], JsonEncoderContextBuilder]"

_START: Context = {STRICT: True, COLLECT_DENORMALIZATION_ERRORS: True}

_SETTINGS: list[tuple[str, _Setting, str, object]] = [
    ("indented", lambda builder: builder.with_indent(2), JSON_INDENT, 2),
    ("on-one-line", lambda builder: builder.with_indent(None), JSON_INDENT, None),
]


@pytest.mark.parametrize(
    ("setting", "key", "value"),
    [(setting, key, value) for _, setting, key, value in _SETTINGS],
    ids=[name for name, _, _, _ in _SETTINGS],
)
def test_each_option_sets_its_own_key_and_no_other(
    setting: _Setting, key: str, value: object
) -> None:
    builder = setting(JsonEncoderContextBuilder(_START))

    assert builder.to_dict() == {**_START, key: value}


def test_setting_an_option_leaves_the_builder_it_was_set_on_as_it_was() -> None:
    builder = JsonEncoderContextBuilder(_START)

    _ = builder.with_indent(2)

    assert builder.to_dict() == _START


def test_setting_an_option_again_replaces_its_value() -> None:
    builder = JsonEncoderContextBuilder().with_indent(2)

    builder = builder.with_indent(4)

    assert builder.to_dict() == {JSON_INDENT: 4}


def test_the_context_it_built_starts_an_equal_builder() -> None:
    built = JsonEncoderContextBuilder(_START).with_indent(2).to_dict()

    assert JsonEncoderContextBuilder(built).to_dict() == built
