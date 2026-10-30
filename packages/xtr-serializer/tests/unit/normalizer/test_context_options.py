"""A call's context read as the options pydantic writes and reads with."""

from __future__ import annotations

import pytest

from xtr_serializer.exception import InvalidArgumentError
from xtr_serializer.normalizer import (
    ALLOW_EXTRA_ATTRIBUTES,
    BY_ALIAS,
    IGNORED_ATTRIBUTES,
    POPULATE_BY_NAME,
    SKIP_NULL_VALUES,
    STRICT,
)
from xtr_serializer.normalizer._context_options import (
    ReadOptions,
    WriteOptions,
    read_options,
    write_options,
)


def test_an_empty_context_writes_everything_under_the_alias() -> None:
    options = write_options({})

    assert options == WriteOptions(None, None, True, False, False, False)
    assert not options.partial


@pytest.mark.parametrize(
    "context",
    [{IGNORED_ATTRIBUTES: {"a"}}, {SKIP_NULL_VALUES: True}],
    ids=["ignored", "skipped"],
)
def test_leaving_anything_out_is_a_partial_write(context: dict[str, object]) -> None:
    assert write_options(context).partial


def test_an_empty_context_reads_under_the_alias_leaving_the_type_its_own_rules() -> None:
    assert read_options({}) == ReadOptions(None, None, True, None, False, False)


def test_without_the_alias_it_reads_under_the_name() -> None:
    options = read_options({BY_ALIAS: False, ALLOW_EXTRA_ATTRIBUTES: False})

    assert (options.by_alias, options.by_name, options.extra) == (False, True, "forbid")


def test_it_refuses_an_option_of_the_wrong_type() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = write_options({IGNORED_ATTRIBUTES: ["a"]})


def test_of_several_reading_options_of_the_wrong_type_it_names_strict_first() -> None:
    with pytest.raises(InvalidArgumentError, match=repr(STRICT)):
        _ = read_options({ALLOW_EXTRA_ATTRIBUTES: 1, BY_ALIAS: 1, STRICT: 1})


def test_it_refuses_a_name_option_of_the_wrong_type_with_aliases_off() -> None:
    with pytest.raises(InvalidArgumentError, match=repr(POPULATE_BY_NAME)):
        _ = read_options({BY_ALIAS: False, POPULATE_BY_NAME: 1})
