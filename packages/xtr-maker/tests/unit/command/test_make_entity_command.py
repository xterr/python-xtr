"""Unit tests for :class:`xtr_maker.command.make_entity_command.MakeEntityCommand`."""

from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

import pytest
from typing_extensions import Unpack
from xtr_console import ExitCode

from tests.conftest import FIXTURES
from tests.support.captured_style import CapturedStyle
from xtr_maker import FileManager, Generator, TemplateRenderer
from xtr_maker.command.make_entity_command import MakeEntityCommand

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_EXPECTED = FIXTURES / "expected" / "entity"
_BOOK = "src/app/entity/book.py"
_AUTHOR = "src/app/entity/author.py"
_BOOK_REPOSITORY = "src/app/repository/book_repository.py"
_BOOK_FLAGS = ["title:string:120", "price:decimal:10:2", "published_at:datetime?"]
_BOOK_RELATION = ["author:many_to_one:Author,inverse=books"]


class _Options(TypedDict, total=False):
    """The command's options a test passes."""

    fields: list[str]
    relations: list[str]
    id_type: str
    no_audit: bool


async def _run(
    project: Path,
    style: CapturedStyle,
    name: str | None = None,
    *,
    final_classes: bool = True,
    **options: Unpack[_Options],
) -> int:
    manager = FileManager(project, "app")
    renderer = TemplateRenderer()
    generator = Generator(manager, renderer, final_classes=final_classes)
    command = MakeEntityCommand(manager, renderer)
    return await command(style.io, generator, name, **options)


def _read(project: Path, path: str) -> str:
    return (project / path).read_text(encoding="utf-8")


def _expected(name: str) -> str:
    return (_EXPECTED / name).read_text(encoding="utf-8")


def _batch() -> CapturedStyle:
    return CapturedStyle(interactive=False)


async def _author_and_book(project: Path) -> None:
    assert await _run(project, _batch(), "Author", fields=["name:string:120"]) == ExitCode.SUCCESS
    code = await _run(project, _batch(), "Book", fields=_BOOK_FLAGS, relations=_BOOK_RELATION)
    assert code == ExitCode.SUCCESS


async def test_flags_write_the_entity_its_repository_and_the_inverse(project: Path) -> None:
    await _author_and_book(project)

    assert _read(project, _BOOK) == _expected("book.py.txt")
    assert _read(project, _BOOK_REPOSITORY) == _expected("book_repository.py.txt")
    assert _read(project, _AUTHOR) == _expected("author.py.txt")


async def test_fields_added_to_an_existing_entity_change_only_their_lines(project: Path) -> None:
    (project / "src/app/entity").mkdir()
    _ = (project / "src/app/entity/order.py").write_text(
        _expected("order_before.py.txt"), encoding="utf-8"
    )
    style = _batch()

    code = await _run(project, style, "Order", fields=["note:text?", "placed_at:datetime"])

    assert code == ExitCode.SUCCESS
    assert _read(project, "src/app/entity/order.py") == _expected("order_after.py.txt")
    assert not (project / "src/app/repository").exists()
    assert "updated: src/app/entity/order.py" in style.output


async def test_answers_add_fields_and_a_relation(project: Path) -> None:
    assert await _run(project, _batch(), "Author") == ExitCode.SUCCESS
    style = CapturedStyle(
        [
            "Book",
            "title",
            "",
            "120",
            "n",
            "class",
            "author",
            "relation",
            "many_to_one",
            "Author",
            "n",
            "",
            "",
        ]
    )

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert "'class' cannot name a property" in style.output
    assert '    author: Mapped[Author] = relationship(back_populates="books")\n' in _read(
        project, _BOOK
    )
    assert "    books: Mapped[list[Book]]" in _read(project, _AUTHOR)


async def test_the_key_and_the_audit_columns_pick_the_base(project: Path) -> None:
    code = await _run(project, _batch(), "Tag", id_type="bigint", no_audit=True)

    assert code == ExitCode.SUCCESS
    source = _read(project, "src/app/entity/tag.py")
    assert "class Tag(BigIntBase):" in source
    assert "Its ``id`` comes from the base" in source


async def test_classes_are_left_open_when_final_classes_is_off(project: Path) -> None:
    code = await _run(project, _batch(), "Book", final_classes=False)

    assert code == ExitCode.SUCCESS
    assert "final" not in _read(project, _BOOK)
    assert "final" not in _read(project, _BOOK_REPOSITORY)


async def test_the_next_steps_name_the_migration_commands(project: Path) -> None:
    style = _batch()

    _ = await _run(project, style, "Book")

    assert style.lines[-3:] == [
        "Next:",
        "- Run make:migration to write the revision the change needs.",
        "- Then run orm:migrations:migrate -n to apply it.",
    ]


async def test_nothing_added_to_an_existing_entity_writes_nothing(project: Path) -> None:
    _ = await _run(project, _batch(), "Book")
    before = _read(project, _BOOK)
    style = _batch()

    code = await _run(project, style, "Book")

    assert code == ExitCode.SUCCESS
    assert "Nothing was added to Book." in style.output
    assert _read(project, _BOOK) == before


async def test_without_a_terminal_a_missing_name_is_refused(project: Path) -> None:
    style = _batch()

    assert await _run(project, style) == ExitCode.INVALID
    assert "make:entity <name>" in style.output


@pytest.mark.parametrize(
    ("options", "reason"),
    [
        ({"id_type": "serial"}, "There is no key type 'serial'"),
        ({"fields": ["title:words"]}, "There is no field type 'words'"),
        ({"fields": ["title", "title"]}, "Book already has a property 'title'"),
        ({"fields": ["id:uuid"]}, "the base class already provides it"),
        ({"relations": ["author:many_to_one:Author"]}, "make it first with make:entity Author"),
    ],
)
async def test_a_refused_option_writes_nothing(
    project: Path, options: _Options, reason: str
) -> None:
    style = _batch()

    code = await _run(project, style, "Book", **options)

    assert code == ExitCode.INVALID
    assert reason in style.output
    assert not (project / "src/app/entity").exists()


async def test_the_base_options_are_refused_for_an_existing_entity(project: Path) -> None:
    _ = await _run(project, _batch(), "Book")
    style = _batch()

    code = await _run(project, style, "Book", id_type="uuid7", fields=["title"])

    assert code == ExitCode.INVALID
    assert "--id and --no-audit only choose a new entity's base" in style.output
    assert "title" not in _read(project, _BOOK)


async def test_an_existing_repository_is_refused_and_nothing_is_written(project: Path) -> None:
    (project / "src/app/repository").mkdir()
    _ = (project / _BOOK_REPOSITORY).write_text('"""Mine."""\n', encoding="utf-8")
    style = _batch()

    code = await _run(project, style, "Book", fields=["title"])

    assert code == ExitCode.FAILURE
    assert "book_repository.py already exists" in style.output
    assert not (project / _BOOK).exists()


async def test_an_existing_association_table_is_refused(project: Path) -> None:
    _ = await _run(project, _batch(), "Tag")
    _ = (project / "src/app/entity/book_tag.py").write_text('"""Mine."""\n', encoding="utf-8")
    style = _batch()

    code = await _run(project, style, "Book", relations=["tags:many_to_many:Tag"])

    assert code == ExitCode.FAILURE
    assert not (project / _BOOK).exists()
