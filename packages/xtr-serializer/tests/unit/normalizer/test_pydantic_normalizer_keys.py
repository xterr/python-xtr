"""The pydantic normalizer's keys are spelled as a context carries them."""

from __future__ import annotations

from xtr_serializer.normalizer.pydantic_normalizer_keys import (
    ALLOW_EXTRA_ATTRIBUTES,
    ATTRIBUTES,
    BY_ALIAS,
    FROM_ATTRIBUTES,
    IGNORED_ATTRIBUTES,
    POPULATE_BY_NAME,
    SKIP_DEFAULT_VALUES,
    SKIP_NULL_VALUES,
    SKIP_UNSET_VALUES,
    STRICT,
)


def test_each_key_is_spelled_as_a_context_carries_it() -> None:
    assert [
        ATTRIBUTES,
        IGNORED_ATTRIBUTES,
        SKIP_NULL_VALUES,
        SKIP_UNSET_VALUES,
        SKIP_DEFAULT_VALUES,
        BY_ALIAS,
        STRICT,
        ALLOW_EXTRA_ATTRIBUTES,
        FROM_ATTRIBUTES,
        POPULATE_BY_NAME,
    ] == [
        "attributes",
        "ignored_attributes",
        "skip_null_values",
        "skip_unset_values",
        "skip_default_values",
        "by_alias",
        "strict",
        "allow_extra_attributes",
        "from_attributes",
        "populate_by_name",
    ]
