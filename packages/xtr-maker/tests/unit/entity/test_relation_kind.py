"""Unit tests for :class:`xtr_maker.entity.RelationKind`."""

from __future__ import annotations

from xtr_maker.entity import RelationKind


def test_the_many_side_holds_the_key() -> None:
    assert {kind for kind in RelationKind if kind.holds_key} == {
        RelationKind.MANY_TO_ONE,
        RelationKind.ONE_TO_ONE,
    }


def test_collections_on_each_side() -> None:
    assert {kind for kind in RelationKind if kind.is_collection} == {
        RelationKind.ONE_TO_MANY,
        RelationKind.MANY_TO_MANY,
    }
    assert {kind for kind in RelationKind if kind.is_inverse_collection} == {
        RelationKind.MANY_TO_ONE,
        RelationKind.MANY_TO_MANY,
    }


def test_only_one_to_many_requires_its_inverse() -> None:
    assert [kind for kind in RelationKind if kind.requires_inverse] == [RelationKind.ONE_TO_MANY]


def test_only_many_to_many_has_no_key_to_leave_empty() -> None:
    assert [kind for kind in RelationKind if not kind.may_be_null] == [RelationKind.MANY_TO_MANY]
