"""Unit tests for :class:`xtr_maker.Generator`."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import FIXTURES
from tests.support.captured_style import CapturedStyle
from xtr_maker import (
    ClassName,
    FileManager,
    GeneratedSourceError,
    Generator,
    TargetExistsError,
    TemplateRenderer,
)

if TYPE_CHECKING:
    from pathlib import Path


def _generator(project: Path, *, final_classes: bool = True) -> Generator:
    return Generator(
        FileManager(project, "app"),
        TemplateRenderer((FIXTURES / "templates",)),
        final_classes=final_classes,
    )


def _handler() -> ClassName:
    return ClassName.create(
        "ordering.place order", root_package="app", kind="message_handler", suffix="Handler"
    )


def test_generate_class_queues_the_module_under_the_package(project: Path) -> None:
    generator = _generator(project)

    target = generator.generate_class(_handler(), "class.py.jinja")

    assert target == project.resolve() / "src/app/message_handler/ordering/place_order_handler.py"
    assert generator.has_pending_operations()
    assert not target.exists()


def test_generate_class_gives_the_template_the_class_its_module_and_the_final_setting(
    project: Path,
) -> None:
    generator = _generator(project, final_classes=False)
    target = generator.generate_class(_handler(), "class.py.jinja")

    generator.write_changes(CapturedStyle().io)

    assert target.read_text(encoding="utf-8") == (
        '"""The PlaceOrderHandler class."""\n'
        "\n"
        "from __future__ import annotations\n"
        "\n"
        "\n"
        "class PlaceOrderHandler:\n"
        '    """Generated into app.message_handler.ordering.place_order_handler; final: False."""\n'
    )


def test_write_changes_writes_every_file_with_the_packages_it_needs(project: Path) -> None:
    generator = _generator(project)
    _ = generator.generate_class(_handler(), "class.py.jinja")
    _ = generator.dump_file("README.txt", "notes\n")
    style = CapturedStyle()

    generator.write_changes(style.io)

    assert style.lines == [
        "created: src/app/message_handler/__init__.py",
        "created: src/app/message_handler/ordering/__init__.py",
        "created: src/app/message_handler/ordering/place_order_handler.py",
        "created: README.txt",
    ]
    assert not generator.has_pending_operations()


def test_generated_files_lists_every_queued_file_after_writing(project: Path) -> None:
    generator = _generator(project)
    first = generator.dump_file("a.txt", "a\n")
    second = generator.generate_file("b.py", "function.py.jinja", {"name": "go"})

    generator.write_changes(CapturedStyle().io)

    assert generator.generated_files == (first, second)


@pytest.mark.parametrize("final_classes", [True, False])
def test_final_classes_reports_the_setting_it_was_built_with(
    project: Path, final_classes: bool
) -> None:
    assert _generator(project, final_classes=final_classes).final_classes is final_classes


def test_a_file_that_exists_is_refused(project: Path) -> None:
    with pytest.raises(TargetExistsError) as raised:
        _ = _generator(project).dump_file("src/app/__init__.py", "x = 1\n")

    assert raised.value.path == "src/app/__init__.py"


def test_a_file_already_queued_is_refused(project: Path) -> None:
    generator = _generator(project)
    _ = generator.generate_class(_handler(), "class.py.jinja")

    with pytest.raises(TargetExistsError, match=r"place_order_handler\.py"):
        _ = generator.generate_class(_handler(), "class.py.jinja")


def test_broken_source_is_refused_before_anything_is_queued(project: Path) -> None:
    generator = _generator(project)

    with pytest.raises(GeneratedSourceError):
        _ = generator.generate_file("b.py", "function.py.jinja", {"name": "not valid"})

    assert not generator.has_pending_operations()
