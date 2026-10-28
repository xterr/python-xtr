"""Options given to a dump replace the defaults key by key, however deep."""

from __future__ import annotations

from xtr_workflow.dumper._options import mapping_at, replace_recursive


def test_a_nested_mapping_is_merged_key_by_key() -> None:
    merged = replace_recursive({"node": {"a": "1", "b": "2"}}, {"node": {"b": "3", "c": "4"}})

    assert merged == {"node": {"a": "1", "b": "3", "c": "4"}}


def test_a_key_keeps_the_place_of_the_default_it_replaces() -> None:
    merged = replace_recursive({"a": "1", "b": "2"}, {"c": "3", "a": "4"})

    assert list(merged) == ["a", "b", "c"]


def test_a_value_that_is_not_a_mapping_replaces_the_default_whole() -> None:
    merged = replace_recursive(
        {"node": {"a": "1"}, "edge": "x"}, {"node": "flat", "edge": {"b": "2"}}
    )

    assert merged == {"node": "flat", "edge": {"b": "2"}}


def test_the_merged_mappings_are_copies() -> None:
    defaults: dict[str, object] = {"node": {"a": "1"}}
    given: dict[str, object] = {"edge": {"b": "2"}}

    merged = replace_recursive(defaults, given)
    node = mapping_at(merged, "node")
    edge = mapping_at(merged, "edge")

    assert node is not defaults["node"]
    assert edge is not given["edge"]


def test_mapping_at_reads_a_nested_mapping() -> None:
    assert mapping_at({"node": {"a": "1"}}, "node") == {"a": "1"}


def test_mapping_at_reads_anything_else_as_empty() -> None:
    assert mapping_at({"node": "flat"}, "node") == {}
    assert mapping_at({}, "node") == {}
