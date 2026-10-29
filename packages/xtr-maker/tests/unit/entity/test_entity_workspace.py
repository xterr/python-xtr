"""Unit tests for :class:`xtr_maker.entity.EntityWorkspace`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.support.captured_style import CapturedStyle
from xtr_maker import ClassName, FileManager, Generator, InvalidArgumentError, TemplateRenderer
from xtr_maker.entity import EntityField, EntityRelation, EntitySourceEditor, EntityWorkspace

if TYPE_CHECKING:
    from pathlib import Path

_AUTHOR = '''"""The ``Author`` entity."""

from __future__ import annotations

from advanced_alchemy.base import UUIDAuditBase

__all__ = ["Author"]


class Author(UUIDAuditBase):
    """One author."""

    __tablename__ = "authors"
'''


def _workspace(project: Path, name: str, *, is_new: bool) -> tuple[EntityWorkspace, Generator]:
    manager = FileManager(project, "app")
    generator = Generator(manager, TemplateRenderer())
    entity = ClassName.create(name, root_package="app", kind="entity")
    path = manager.package_dir / entity.path
    source = _AUTHOR.replace("Author", name).replace("authors", f"{name.lower()}s")
    editor = EntitySourceEditor(source if is_new else path.read_text(encoding="utf-8"), entity)
    return EntityWorkspace(manager, generator, editor, is_new=is_new), generator


def _write_author(project: Path) -> Path:
    (project / "src/app/entity").mkdir(exist_ok=True)
    path = project / "src/app/entity/author.py"
    _ = path.write_text(_AUTHOR, encoding="utf-8")
    return path


def test_a_new_entity_is_queued_even_with_nothing_added(project: Path) -> None:
    workspace, generator = _workspace(project, "Book", is_new=True)

    assert workspace.changed
    assert workspace.queue() == (project.resolve() / "src/app/entity/book.py",)
    assert generator.has_pending_operations()


def test_an_existing_entity_with_nothing_added_has_nothing_to_write(project: Path) -> None:
    _ = _write_author(project)
    workspace, _ = _workspace(project, "Author", is_new=False)

    assert not workspace.changed
    assert workspace.queue() == ()


def test_a_relation_writes_back_the_entity_it_reaches(project: Path) -> None:
    author = _write_author(project)
    workspace, generator = _workspace(project, "Book", is_new=True)
    workspace.add_field(EntityField.parse("title:string:120"))

    workspace.add_relation(EntityRelation.parse("author:many_to_one:Author", "Book"))
    _ = workspace.queue()
    generator.write_changes(CapturedStyle().io)

    assert "books: Mapped[list[Book]]" in author.read_text(encoding="utf-8")
    book = (project / "src/app/entity/book.py").read_text(encoding="utf-8")
    assert "title: Mapped[str]" in book
    assert "author: Mapped[Author]" in book


def test_a_relation_to_a_missing_entity_is_refused(project: Path) -> None:
    workspace, _ = _workspace(project, "Book", is_new=True)

    with pytest.raises(InvalidArgumentError, match="make it first with make:entity Author"):
        workspace.add_relation(EntityRelation.parse("author:many_to_one:Author", "Book"))


def test_taken_reports_the_entity_s_own_names(project: Path) -> None:
    workspace, _ = _workspace(project, "Book", is_new=True)
    workspace.add_field(EntityField.parse("title"))

    assert workspace.taken("title")
    assert not workspace.taken("isbn")
    assert workspace.is_new
