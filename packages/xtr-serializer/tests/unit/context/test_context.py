"""The options of different steps never collide in the one context a call hands them all."""

from __future__ import annotations

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
)


def test_no_two_steps_read_the_same_key() -> None:
    keys = [
        COLLECT_DENORMALIZATION_ERRORS,
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
        JSON_INDENT,
    ]

    assert len(set(keys)) == len(keys)
