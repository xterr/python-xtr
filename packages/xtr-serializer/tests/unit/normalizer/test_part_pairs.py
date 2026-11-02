"""The parts of a container paired with their copies, or settled at once."""

from __future__ import annotations

from xtr_serializer.normalizer._part_pairs import ABSENT, mapping_pairs, pairs, set_pairs


def test_plain_equal_parts_are_settled_at_once() -> None:
    assert pairs([0, 1], [1, "a"], [1, "a"]) is None


def test_parts_of_another_type_are_paired_at_their_places() -> None:
    found = pairs([0], [True], [1])

    assert list(found or []) == [(0, True, 1, None)]


def test_mappings_of_another_size_differ_as_the_mapping() -> None:
    assert mapping_pairs({"a": 1}, {}, dict) is dict


def test_a_key_of_another_type_is_paired_at_the_mapping() -> None:
    found = mapping_pairs({1.0: "a"}, {1: "a"})

    assert not isinstance(found, type)
    assert list(found or []) == [(None, 1.0, 1, dict), (None, "a", "a", None)]


def test_a_member_missing_from_the_copy_is_paired_with_nothing() -> None:
    found = set_pairs({1}, {2}, set)

    assert not isinstance(found, type)
    assert list(found) == [(None, 1, ABSENT, None)]


def test_sets_of_another_size_differ_as_the_set() -> None:
    assert set_pairs({1}, set(), frozenset) is frozenset
