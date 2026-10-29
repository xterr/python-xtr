"""Unit tests for :class:`xtr_maker.entity.RelationWriter`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.captured_style import CapturedStyle
from xtr_maker import (
    ClassName,
    FileManager,
    Generator,
    InvalidArgumentError,
    TargetExistsError,
    TemplateRenderer,
)
from xtr_maker.entity import EntityRelation, EntitySourceEditor, RelationKind, RelationWriter

if TYPE_CHECKING:
    from pathlib import Path

_ENTITY = '''"""The ``{name}`` entity."""

from __future__ import annotations

from advanced_alchemy.base import {base}

__all__ = ["{name}"]


class {name}({base}):
    """One {name}."""

    __tablename__ = "{table}"
'''


def _entity(name: str, base: str = "UUIDAuditBase", table: str | None = None) -> EntitySourceEditor:
    source = _ENTITY.format(name=name, base=base, table=table or f"{name.lower()}s")
    return EntitySourceEditor(source, ClassName.create(name, root_package="app", kind="entity"))


def _generator(project: Path) -> Generator:
    return Generator(FileManager(project, "app"), TemplateRenderer())


def _body(editor: EntitySourceEditor) -> str:
    return editor.source.split('__tablename__ = "', 1)[1].split("\n", 1)[1]


def test_many_to_one_adds_the_key_the_relationship_and_the_inverse(project: Path) -> None:
    book, author = _entity("Book"), _entity("Author", table="writers")
    relation = EntityRelation("author", RelationKind.MANY_TO_ONE, "Author", inverse="books")

    RelationWriter(_generator(project)).write(relation, book, author)

    assert _body(book) == (
        "\n"
        '    author_id: Mapped[UUID] = mapped_column(ForeignKey("writers.id"))\n'
        '    author: Mapped[Author] = relationship(back_populates="books")\n'
    )
    assert "if TYPE_CHECKING:\n    from app.entity.author import Author\n" in book.source
    assert "from uuid import UUID\n" in book.source
    assert (
        _body(author) == '\n    books: Mapped[list[Book]] = relationship(back_populates="author")\n'
    )


def test_a_nullable_key_to_an_integer_key_is_optional_on_both_attributes(project: Path) -> None:
    book, shelf = _entity("Book"), _entity("Shelf", base="BigIntAuditBase")
    relation = EntityRelation("shelf", RelationKind.MANY_TO_ONE, "Shelf", nullable=True)

    RelationWriter(_generator(project)).write(relation, book, shelf)

    assert (
        '    shelf_id: Mapped[int | None] = mapped_column(ForeignKey("shelfs.id"), nullable=True)\n'
        in (book.source)
    )
    assert "    shelf: Mapped[Shelf | None] = relationship()\n" in book.source
    assert shelf.source == _entity("Shelf", base="BigIntAuditBase").source


def test_one_to_one_makes_the_key_unique_and_the_inverse_a_single_optional(project: Path) -> None:
    user, profile = _entity("User"), _entity("Profile")
    relation = EntityRelation("profile", RelationKind.ONE_TO_ONE, "Profile", inverse="user")

    RelationWriter(_generator(project)).write(relation, user, profile)

    assert 'mapped_column(ForeignKey("profiles.id"), unique=True)' in user.source
    assert (
        '    user: Mapped[User | None] = relationship(back_populates="profile")\n' in profile.source
    )


def test_one_to_many_puts_the_key_on_the_other_entity(project: Path) -> None:
    author, book = _entity("Author"), _entity("Book")
    relation = EntityRelation("books", RelationKind.ONE_TO_MANY, "Book", inverse="author")

    RelationWriter(_generator(project)).write(relation, author, book)

    assert (
        _body(author) == '\n    books: Mapped[list[Book]] = relationship(back_populates="author")\n'
    )
    assert _body(book) == (
        "\n"
        '    author_id: Mapped[UUID] = mapped_column(ForeignKey("authors.id"))\n'
        '    author: Mapped[Author] = relationship(back_populates="books")\n'
    )


def test_many_to_many_writes_an_association_table_both_sides_name(project: Path) -> None:
    generator = _generator(project)
    book, tag = _entity("Book"), _entity("Tag", base="BigIntBase")
    relation = EntityRelation("tags", RelationKind.MANY_TO_MANY, "Tag", inverse="books")

    RelationWriter(generator).write(relation, book, tag)
    generator.write_changes(CapturedStyle().io)

    association = (project / "src/app/entity/book_tag.py").read_text(encoding="utf-8")
    assert 'Column[UUID]("book_id", ForeignKey("books.id"), primary_key=True),' in association
    assert 'Column[int]("tag_id", ForeignKey("tags.id"), primary_key=True),' in association
    assert "from app.entity.book_tag import book_tag_table\n" in book.source
    assert "secondary=book_tag_table" in book.source
    assert 'back_populates="tags"' in tag.source


def test_a_self_reference_needs_no_import(project: Path) -> None:
    category = _entity("Category", table="categories")
    relation = EntityRelation("parent", RelationKind.MANY_TO_ONE, "Category", inverse="children")

    RelationWriter(_generator(project)).write(relation, category, category)

    assert "TYPE_CHECKING" not in category.source
    assert '    parent: Mapped[Category] = relationship(back_populates="children")\n' in (
        category.source
    )
    assert '    children: Mapped[list[Category]] = relationship(back_populates="parent")\n' in (
        category.source
    )


def test_a_taken_inverse_is_refused_before_anything_is_added(project: Path) -> None:
    book, author = _entity("Book"), _entity("Author")
    writer = RelationWriter(_generator(project))
    writer.write(
        EntityRelation("writer", RelationKind.MANY_TO_ONE, "Author", inverse="books"), book, author
    )
    before = book.source

    with pytest.raises(InvalidArgumentError, match="Author already has a property 'books'"):
        writer.write(
            EntityRelation("author", RelationKind.MANY_TO_ONE, "Author", inverse="books"),
            book,
            author,
        )
    assert book.source == before


def test_a_self_referencing_many_to_many_is_refused(project: Path) -> None:
    tag = _entity("Tag")

    with pytest.raises(InvalidArgumentError, match="to itself is not supported"):
        RelationWriter(_generator(project)).write(
            EntityRelation("related", RelationKind.MANY_TO_MANY, "Tag", inverse="others"), tag, tag
        )


def test_an_entity_whose_key_cannot_be_told_is_refused(project: Path) -> None:
    book, author = _entity("Book"), _entity("Author", base="DefaultBase")

    with pytest.raises(InvalidArgumentError, match="key type of Author cannot be told"):
        RelationWriter(_generator(project)).write(
            EntityRelation("author", RelationKind.MANY_TO_ONE, "Author"), book, author
        )


def test_an_existing_association_module_is_refused(project: Path) -> None:
    (project / "src/app/entity").mkdir()
    _ = (project / "src/app/entity/book_tag.py").write_text('"""Mine."""\n', encoding="utf-8")
    book, tag = _entity("Book"), _entity("Tag")

    with pytest.raises(TargetExistsError):
        RelationWriter(_generator(project)).write(
            EntityRelation("tags", RelationKind.MANY_TO_MANY, "Tag"), book, tag
        )
    assert "tags" not in _body(book)
