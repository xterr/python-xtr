"""The pydantic normalizer's keys are spelled as an application writes them in a context."""

from __future__ import annotations

from typing import cast

from xtr_serializer.normalizer import pydantic_normalizer_keys as keys


def test_every_key_is_spelled_as_an_application_writes_it() -> None:
    spellings = {name: cast("object", getattr(keys, name)) for name in keys.__all__}

    assert spellings == {
        "ALLOW_EXTRA_ATTRIBUTES": "allow_extra_attributes",
        "ATTRIBUTES": "attributes",
        "BY_ALIAS": "by_alias",
        "FROM_ATTRIBUTES": "from_attributes",
        "IGNORED_ATTRIBUTES": "ignored_attributes",
        "POPULATE_BY_NAME": "populate_by_name",
        "SKIP_DEFAULT_VALUES": "skip_default_values",
        "SKIP_NULL_VALUES": "skip_null_values",
        "SKIP_UNSET_VALUES": "skip_unset_values",
        "STRICT": "strict",
    }
