"""The serializer's context builder sets its one option and leaves every other key alone."""

from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_serializer import COLLECT_DENORMALIZATION_ERRORS, JSON_INDENT, SerializerContextBuilder

if TYPE_CHECKING:
    from xtr_serializer import Context

_START: Context = {JSON_INDENT: 2}


def test_collecting_every_error_sets_that_key_and_no_other() -> None:
    builder = SerializerContextBuilder(_START).with_collect_denormalization_errors(True)

    assert builder.to_dict() == {**_START, COLLECT_DENORMALIZATION_ERRORS: True}


def test_setting_an_option_leaves_the_builder_it_was_set_on_as_it_was() -> None:
    builder = SerializerContextBuilder(_START)

    _ = builder.with_collect_denormalization_errors(True)

    assert builder.to_dict() == _START


def test_setting_an_option_again_replaces_its_value() -> None:
    builder = SerializerContextBuilder().with_collect_denormalization_errors(True)

    builder = builder.with_collect_denormalization_errors(False)

    assert builder.to_dict() == {COLLECT_DENORMALIZATION_ERRORS: False}


def test_the_context_it_built_starts_an_equal_builder() -> None:
    built = SerializerContextBuilder(_START).with_collect_denormalization_errors(True).to_dict()

    assert SerializerContextBuilder(built).to_dict() == built
