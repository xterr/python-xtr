from __future__ import annotations

from typing import TYPE_CHECKING, cast

import pytest

from xtr_http_client.exception import InvalidArgumentError
from xtr_http_client.internal.query import build_query, merge_query_string

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import QueryValue


def test_nothing_to_merge_leaves_the_query_string_as_it_was() -> None:
    assert merge_query_string("a=b", {}, replace=True) == "a=b"
    assert merge_query_string(None, {}, replace=True) is None


def test_a_parameter_the_url_already_carries_wins_when_nothing_is_replaced() -> None:
    assert merge_query_string("a=1", {"a": 2, "b": 3}, replace=False) == "a=1&b=3"


def test_a_parameter_the_url_already_carries_loses_when_replacing() -> None:
    assert merge_query_string("a=1", {"a": 2, "b": 3}, replace=True) == "a=2&b=3"


def test_a_parameter_of_none_drops_the_one_the_url_carried() -> None:
    assert merge_query_string("a=1&b=2", {"a": None}, replace=True) == "b=2"
    assert merge_query_string("a=1&b=2", {"a": None}, replace=False) == "a=1&b=2"


def test_a_sequence_repeats_the_name_and_a_mapping_names_its_sub_keys() -> None:
    assert build_query({"tag": ["new", "sale"]}, option="query") == "tag=new&tag=sale"
    assert build_query({"page": {"size": 10}}, option="query") == "page[size]=10"


def test_a_boolean_is_sent_as_one_or_zero_and_none_is_not_sent_at_all() -> None:
    assert build_query({"a": True, "b": False, "c": None}, option="query") == "a=1&b=0"


def test_a_form_encodes_a_space_as_a_plus_and_a_query_as_a_percent() -> None:
    assert build_query({"a": "b c"}, option="body", form=True) == "a=b+c"
    assert build_query({"a": "b c"}, option="query") == "a=b%20c"


def test_an_empty_collection_contributes_nothing() -> None:
    assert build_query({"a": {}, "b": [], "c": "d"}, option="query") == "c=d"


def test_a_value_that_is_neither_a_scalar_nor_a_collection_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = build_query(cast("Mapping[str, QueryValue]", {"a": object()}), option="body")

    assert str(raised.value) == (
        'Invalid value for option "body": "object" is not a scalar, a sequence or a mapping.'
    )
