"""Unit tests for :class:`xtr_maker.entity.EntityInterviewer`."""

from __future__ import annotations

import pytest

from tests.support.captured_style import CapturedStyle
from xtr_maker import InvalidArgumentError
from xtr_maker.entity import EntityField, EntityInterviewer, EntityRelation, FieldType, RelationKind


def _ask(*answers: str, taken: tuple[str, ...] = ()) -> EntityField | EntityRelation | None:
    style = CapturedStyle(answers)
    return EntityInterviewer(style.io, "Book").next_member(taken.__contains__)


def test_an_empty_name_ends_the_questions() -> None:
    assert _ask("") is None


def test_a_string_takes_its_length_and_nullability() -> None:
    assert _ask("title", "", "120", "y") == EntityField(
        "title", FieldType.STRING, nullable=True, length=120
    )


def test_the_type_offered_follows_the_name() -> None:
    assert _ask("published_at", "", "n") == EntityField("published_at", FieldType.DATETIME)


def test_a_decimal_takes_its_precision_and_scale() -> None:
    field = _ask("price", "decimal", "12", "3", "n")

    assert field == EntityField("price", FieldType.DECIMAL, precision=12, scale=3)


def test_an_enum_takes_its_class() -> None:
    field = _ask("status", "enum", "http.HTTPStatus", "n")

    assert field == EntityField("status", FieldType.ENUM, enum_class="http.HTTPStatus")


def test_a_question_mark_lists_the_types_then_asks_again() -> None:
    style = CapturedStyle(("note", "?", "text", "n"))

    field = EntityInterviewer(style.io, "Book").next_member(lambda _: False)

    assert field == EntityField("note", FieldType.TEXT)
    assert "big_integer" in style.output
    assert "many_to_one" in style.output


def test_relation_asks_its_kind_target_key_and_inverse() -> None:
    relation = _ask("author", "relation", "many_to_one", "Author", "y", "")

    assert relation == EntityRelation(
        "author", RelationKind.MANY_TO_ONE, "Author", nullable=True, inverse="books"
    )


def test_a_kind_typed_as_the_type_is_a_relation_and_none_skips_the_inverse() -> None:
    relation = _ask("tags", "many_to_many", "Tag", "none")

    assert relation == EntityRelation("tags", RelationKind.MANY_TO_MANY, "Tag")


def test_one_to_many_asks_for_the_property_holding_the_key() -> None:
    style = CapturedStyle(("chapters", "one_to_many", "Chapter", "n", ""))

    relation = EntityInterviewer(style.io, "Book").next_member(lambda _: False)

    assert relation == EntityRelation(
        "chapters", RelationKind.ONE_TO_MANY, "Chapter", inverse="book"
    )
    assert "The property on Chapter that holds the key to Book" in style.output


@pytest.mark.parametrize(
    ("answers", "reason"),
    [
        (("title",), "already has a property 'title'"),
        (("class",), "keyword"),
        (("label", "words"), "There is no field type 'words'"),
        (("label", "string", "long"), "is not a whole number"),
        (("status", "enum", "http.Nothing"), "names no enum"),
        (("author", "relation", "many_to_one", ""), "Name the entity"),
    ],
)
def test_an_answer_that_cannot_be_used_is_refused(answers: tuple[str, ...], reason: str) -> None:
    with pytest.raises(InvalidArgumentError, match=reason):
        _ = _ask(*answers, taken=("title",))
