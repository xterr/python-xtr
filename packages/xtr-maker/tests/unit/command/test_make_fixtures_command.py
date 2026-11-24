"""Unit tests for :class:`xtr_maker.command.make_fixtures_command.MakeFixturesCommand`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from xtr_console import ExitCode

from tests.conftest import FIXTURES
from tests.support.captured_style import CapturedStyle
from xtr_maker import FileManager, Generator, TemplateRenderer
from xtr_maker.command.make_fixtures_command import MakeFixturesCommand

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_EXPECTED = FIXTURES / "expected" / "fixtures"
_FIXTURE = "src/app/fixtures/app_fixtures.py"


async def _run(
    project: Path, style: CapturedStyle, name: str | None = None, *, final_classes: bool = True
) -> int:
    manager = FileManager(project, "app")
    generator = Generator(manager, TemplateRenderer(), final_classes=final_classes)
    return await MakeFixturesCommand(manager)(style.io, generator, name)


def _read(project: Path, path: str) -> str:
    return (project / path).read_text(encoding="utf-8")


async def test_writes_a_fixture_class(project: Path) -> None:
    code = await _run(project, CapturedStyle(interactive=False), "AppFixtures")

    assert code == ExitCode.SUCCESS
    assert _read(project, _FIXTURE) == (_EXPECTED / "app_fixtures.py.txt").read_text(
        encoding="utf-8"
    )


async def test_the_suffix_is_added_to_a_name_without_it(project: Path) -> None:
    code = await _run(project, CapturedStyle(interactive=False), "books")

    assert code == ExitCode.SUCCESS
    assert "class BooksFixtures(Fixture):" in _read(project, "src/app/fixtures/books_fixtures.py")


async def test_writes_into_a_named_package(project: Path) -> None:
    code = await _run(project, CapturedStyle(interactive=False), "catalog.BookFixtures")

    assert code == ExitCode.SUCCESS
    assert "class BookFixtures(Fixture):" in _read(
        project, "src/app/fixtures/catalog/book_fixtures.py"
    )


async def test_the_name_asked_for_defaults_to_app_fixtures(project: Path) -> None:
    style = CapturedStyle([""])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert "AppFixtures" in style.output
    assert (project / _FIXTURE).is_file()


async def test_refuses_an_existing_file(project: Path) -> None:
    (project / "src/app/fixtures").mkdir()
    _ = (project / _FIXTURE).write_text('"""Mine."""\n', encoding="utf-8")
    style = CapturedStyle(interactive=False)

    code = await _run(project, style, "AppFixtures")

    assert code == ExitCode.FAILURE
    assert "src/app/fixtures/app_fixtures.py already exists" in style.output
    assert _read(project, _FIXTURE) == '"""Mine."""\n'


async def test_requires_a_name_without_a_terminal(project: Path) -> None:
    style = CapturedStyle(interactive=False)

    code = await _run(project, style)

    assert code == ExitCode.INVALID
    assert "make:fixtures <name>" in style.output
    assert not (project / "src/app/fixtures").exists()


async def test_an_invalid_name_is_refused(project: Path) -> None:
    style = CapturedStyle(interactive=False)

    code = await _run(project, style, "app!")

    assert code == ExitCode.INVALID
    assert "'app!'" in style.output
    assert not (project / "src/app/fixtures").exists()


async def test_an_invalid_answer_is_asked_again(project: Path) -> None:
    style = CapturedStyle(["app!", "books"])

    code = await _run(project, style)

    assert code == ExitCode.SUCCESS
    assert (project / "src/app/fixtures/books_fixtures.py").is_file()


async def test_the_name_is_asked_three_times_at_most(project: Path) -> None:
    code = await _run(project, CapturedStyle(["a!", "b?", "c#", "books"]))

    assert code == ExitCode.INVALID
    assert not (project / "src/app/fixtures").exists()


async def test_the_class_is_left_open_when_final_classes_is_off(project: Path) -> None:
    code = await _run(project, CapturedStyle(interactive=False), "AppFixtures", final_classes=False)

    assert code == ExitCode.SUCCESS
    assert "final" not in _read(project, _FIXTURE)


async def test_the_next_steps_name_the_file_and_the_command(project: Path) -> None:
    style = CapturedStyle(interactive=False)

    _ = await _run(project, style, "AppFixtures")

    assert style.lines[-3:] == [
        "Next:",
        f"- Open {_FIXTURE} and add the objects it seeds.",
        "- Load them with orm:fixtures:load.",
    ]
