"""Unit tests for :class:`xtr_maker.entity.EntityRelation`."""

from __future__ import annotations

import pytest

from xtr_maker import InvalidArgumentError
from xtr_maker.entity import EntityRelation, RelationKind


def test_a_relation_reads_its_name_kind_target_and_inverse() -> None:
    relation = EntityRelation.parse("author:many_to_one:Author,inverse=writings", "Book")

    assert relation == EntityRelation(
        "author", RelationKind.MANY_TO_ONE, "Author", inverse="writings"
    )


def test_a_question_mark_after_the_target_makes_the_key_nullable() -> None:
    relation = EntityRelation.parse("author:many_to_one:Author?", "Book")

    assert relation.nullable
    assert relation.target == "Author"


def test_a_left_out_inverse_is_the_default_one() -> None:
    assert EntityRelation.parse("author:many_to_one:Author", "Book").inverse == "books"
    assert EntityRelation.parse("books:one_to_many:Book", "Author").inverse == "author"


def test_inverse_none_adds_no_inverse() -> None:
    assert EntityRelation.parse("author:many_to_one:Author,inverse=none", "Book").inverse is None


@pytest.mark.parametrize(
    ("kind", "owner", "expected"),
    [
        (RelationKind.MANY_TO_ONE, "OrderItem", "order_items"),
        (RelationKind.ONE_TO_MANY, "Author", "author"),
        (RelationKind.MANY_TO_MANY, "Book", "books"),
        (RelationKind.ONE_TO_ONE, "User", "user"),
    ],
)
def test_the_default_inverse_follows_the_owner(
    kind: RelationKind, owner: str, expected: str
) -> None:
    assert EntityRelation.default_inverse(kind, owner) == expected


def test_the_key_is_named_after_the_relation() -> None:
    assert EntityRelation("author", RelationKind.MANY_TO_ONE, "Author").key_name == "author_id"


@pytest.mark.parametrize(
    ("typed", "reason"),
    [
        ("author:Author", "does not read as a relation"),
        ("author:many_to_one:Author,mapped=x", "does not read as a relation"),
        ("author:belongs_to:Author", "There is no relation kind 'belongs_to'"),
        ("books:one_to_many:Book,inverse=none", "needs the property on Book"),
        ("tags:many_to_many:Tag?", "no key to leave empty"),
        ("class:many_to_one:Author", "keyword"),
        ("author:many_to_one:Author,inverse=id", "base class already provides it"),
    ],
)
def test_a_relation_that_cannot_be_written_is_refused(typed: str, reason: str) -> None:
    with pytest.raises(InvalidArgumentError, match=reason):
        _ = EntityRelation.parse(typed, "Book")
