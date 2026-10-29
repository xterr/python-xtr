"""A context maps option names to values, and the options of different steps never collide."""

from __future__ import annotations

from collections.abc import Mapping
from typing import get_args, get_origin

from xtr_serializer import (
    ALLOW_EXTRA_ATTRIBUTES,
    ATTRIBUTES,
    BY_ALIAS,
    COLLECT_DENORMALIZATION_ERRORS,
    FROM_ATTRIBUTES,
    IGNORED_ATTRIBUTES,
    JSON_ALLOW_INF_NAN,
    JSON_INDENT,
    POPULATE_BY_NAME,
    SKIP_DEFAULT_VALUES,
    SKIP_NULL_VALUES,
    SKIP_UNSET_VALUES,
    STRICT,
    Context,
)


def test_it_maps_option_names_to_values_of_any_type() -> None:
    assert get_origin(Context) is Mapping
    assert get_args(Context) == (str, object)


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
        JSON_ALLOW_INF_NAN,
    ]

    assert len(set(keys)) == len(keys)
